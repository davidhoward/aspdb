'''
Created on May 10, 2011

@author: david
'''

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
import xml.etree.ElementTree
import urlparse
import util
import logging

class Platform(db.Model):
    @staticmethod
    def from_data(data):
        if data['type'] == 'CPU':
            rec = db.GqlQuery('Select * from CPURecord where vendorID = :1 and cpuFamily = :2 and model = :3', data['vendorID'], data['cpuFamily'], data['model'])
            platform = rec.get()
            if platform is None:
                platform = CPURecord(**data)
                platform.put()
            return platform

class CPURecord(Platform):
    numCores = db.IntegerProperty()
    vendorID = db.StringProperty()
    model = db.IntegerProperty()
    cpuFamily = db.IntegerProperty()
    cacheSize = db.IntegerProperty()
    capabilities = db.StringListProperty()
    
    def similarity(self, other):
        if type(other) is not CPURecord:
            return 0.1
        if other == self:
            return 1.0
        same_caps = 0
        for cap in self.capabilities:
            if cap in other.capabilities:
                same_caps +=1
        m_vec = map(float, [self.numCores, self.cacheSize, len(self.capabilities)])
        o_vec = map(float, [other.numCores, other.cacheSize, same_caps])
        return util.dot(m_vec, o_vec)/util.dot(m_vec, m_vec)
        

class Record (db.Expando):
    platform  = db.ReferenceProperty()
    def __getitem__(self, key):
        try:
            return getattr(self,key)
        except AttributeError:
            return getattr(self.parent(), key)
    def __iter__(self, key):
        return iter(self.parent().properties())
        
class SpecTable(db.Expando):
    key_fields = db.StringListProperty()
    pass

class BottledFunc(db.Model):
    spec_name = db.StringProperty()
    mod_name = db.StringProperty()
    func_name = db.StringProperty()


def get_sim_func(name, specname):
    func_name, mod_name = name.split('.')
    f = db.GqlQuery('select * from BottledFunc where func_name = :1 and spec_name = :2 and mod_name = :3', func_name, specname, mod_name).get()
    if not f:
        return lambda a,b: a.platform.similarity(b.platform)
    else:
        mod_name = f.mod_name
        func_name = f.func_name
        mod = __import__(mod_name)
        return mod.getattr(func_name)
    


def find(specname, sample, similarity, tolerance = 0.0):
    spec = db.get(db.Key.from_path('SpecTable',specname))
    if not spec:
        raise ValueError("Specialiser '%s' not registered" % specname)
    table = db.query_descendants(spec)
    f = get_sim_func(similarity, specname)
    platform = Platform.from_data(sample['platform'])
    sampleRec = Record(parent = spec, platform = platform, **sample['data'])
    logging.debug('Specialiser properties: %s' % spec.key_fields)
    return map(lambda result: dict([(key,result[key]) for key in spec.key_fields]), filter(lambda record: (f(sampleRec, record) >= tolerance), table) )

def update(specname, data):
    spec = db.get(db.Key.from_path('SpecTable',specname))
    platform = Platform.from_data(data['platform'])
    record = Record(parent = spec, platform = platform, **data['data'])
    record.put()
    return []
    
    
def generate_table_structure(key_structure):
    d = {}
    for kv in key_structure:
        d[kv] = type2prop[type(key_structure[kv])](default = key_structure[kv])
    return d

def register(specname, key_structure):
    logging.debug("In register, specname = %s" % specname)
    spec = db.get(db.Key.from_path('SpecTable',specname))
    if spec is None:
        spec = SpecTable(key_name = specname, key_fields = map(lambda a: a, key_structure['data']), **key_structure['data'])
        spec.put()
    else:
        raise ValueError('A specialiser with the name %s already exists' % specname)
    return []
    
def modify(specname, key_structure):
    spec = db.get(db.Key.from_path('SpecTable',specname))
    if spec is None:
        raise ValueError('No specialiser with the name %s exists' % specname)
    else:
        table = generate_table_structure(key_structure)
        for prop in table.iteritems():
            setattr(spec, prop[0], prop[1])
        spec.put()
    return []

prefix2type = {
            'f_':float,
            'i_':int,
            's_':str,
            'd_':dict,
            'l_':list,
            'L_':long
            }
type2prop = {
             int:db.IntegerProperty,
             float:db.FloatProperty,
             str:db.StringProperty,
             long:db.IntegerProperty
             }

def tupelate(dstring):
    s = dstring.strip('{}')
    sl = s.split(", ")
    return map(lambda thing: tuple(map(lambda thing2: thing2.strip("' "), thing.split(':'))), sl)
def parse_proper(kv):
    """
    Perform a second-level decoding of url query string to type-rectify values.
    
    The urlparse module parses a url query string into a dictionary mapping string keys
    to list of string values. This function returns keys to their unmangled values, and
    casts values to their appropriate type.
    
    Input:
        kv: A dictionary generated by urlparse.parse_qs() from a query generated by an
            asp_client application.
    
    Output:
        A new dictionary mapping unmangled names to appropriately typed values.
    
    """
#    logging.debug('raw parsed arguments %s' % kv)
    ret = {}
    for key in kv:
        t = prefix2type[key[:2]]
        if t is dict:
            recurse = kv[key]          
            if type(recurse) is str:
                #this is dangerous. but its also fast.
                recurse = eval(recurse)
            ret[key[2:]] = parse_proper(recurse)
        elif t is list:
            ret[key[2:]] = map(lambda pac: prefix2type[pac[:2]](pac[2:]), kv[key])
        else:
            ret[key[2:]] = t(kv[key])
#    logging.debug('proper-parsed arguments: %s' % ret)
    return ret

post_ops = {
            'update':update,
            'register':register,
            'modify':modify
            }
def invalid_op(op):
    def raiser(a,b):
        raise ValueError('Unsupported operation: %s' % op)
    return raiser
class ASPHandler(webapp.RequestHandler):
    def get(self, *extra):
        '''
        Handles HTTP GET requests to the service, corresponding to aspdb find requests.
        '''
        specname, args = self.extract_request()
        logging.debug('args demarshalled as %s' % args)
        sim_name= args.setdefault('sim_name',None) 
        tolerance = args.setdefault('tolerance',0.0)
        if sim_name is not None:
            args.__delitem__('sim_name')
        if tolerance:
            args.__delitem__('tolerance')
        info = []
        results = []
        try:
            results = find(sample = args, specname = specname, similarity = sim_name, tolerance = tolerance)
        except Exception as e:
            logging.debug("error encountered", exc_info=True)
            info.append((type(e),e.message))
        self.finish(info, results)
        
    def post(self, *extra):
        specname, args = self.extract_request()
        info = []
        results = []
        try:
            exe = post_ops.setdefault(args['op'],invalid_op(args['op']))
            results = exe(specname, args)
        except Exception as e:
            logging.debug("error encountered", exc_info=True)
            info.append((type(e),e.message))
        self.finish(info, results)
        
    def finish(self, info, results):
        """
        Packages the info and results from a query as xml and sends the xml to the 
        requesting host.
        
        
        """
        e_info = xml.etree.ElementTree.Element("info")
        e_results = xml.etree.ElementTree.Element("results")
        for result in results:
            logging.debug("adding result %s" % result)
            e_results.append(util.dictToXML(result, "result"))
        for i in info:
            logging.debug("adding info %s,%s" % i)
            e_info.append(util.dictToXML({'type':i[0], 'reason':i[1]}, "info"))
        e_root = xml.etree.ElementTree.Element("root")
        #The following is python 2.5 compliant, so it works with appengine.
        e_root.append(e_info)
        e_root.append(e_results)
        tree = xml.etree.ElementTree.ElementTree(element = e_root)
        logging.debug("About to write etree")
        logging.debug(xml.etree.ElementTree.tostring(e_root))
        tree.write(self.response.out)
    def extract_request(self):
        path = self.request.path
        logging.debug("path = %s" % path)
        query = self.request.query_string
        specname = path.split('/')[1]
        logging.debug("specname = %s" % specname)
        d = urlparse.parse_qs(query)
        d = util.flatten(d)
        dd = parse_proper(d)
        return specname, dd
    
    
application = webapp.WSGIApplication([('/(.*)/record(.*)', ASPHandler)])

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()