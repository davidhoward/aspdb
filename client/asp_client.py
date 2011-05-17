import asp.config
import time
import urllib2
import urllib
import xml.etree.ElementTree

ASP_host = 'localhost'
ASP_port = 0xadb
retries = 10

class XMLWrapper(object):
    def __init__(self, element):
        self.element = element
    def __getitem__(self, key):
        val = self.element.find(key)
        return str2type[val.get('type')](val.get('val'))
    
class ClientDB:
    MODE_LATENT = 0
    MODE_READ = 1
    MODE_READ_WRITE = 2
    MODE_ADMINISTRATOR = 4
    def __init__(self, specname):

        self.specname = specname
        self.host = pick_host()
        self.platform = asp.config.PlatformDetector()
        self.__authenticated = False
        self.records, self.response = None, None
        
    def connect(self, mode = -1):
        self.connected = True
    
   
    def send_http(self, args, post = False):
        url = self.host + ('/%s/record?' % self.specname) + urllib.urlencode(args)
        if post:
            return urllib2.urlopen(url, str(time.time()))
        else:
            return urllib2.urlopen(url)

    def register_specialiser(self, specname, key_structure):
        if type(key_structure) is not dict:
            raise ValueError('key_structure must be a dictionary mapping key properties to default values')
        args = {'op':'register','data':key_structure}
        args = mangle(args)
        response = self.send_http(args, post = True)
        rtree = xml.etree.ElementTree.ElementTree(file = response)
        info = rtree.getroot().find('info')
        if len(info) > 0:
            print "Operation completed with errors:"
            for sub in map(XMLWrapper, info):
                print sub['reason']
        else:
            print "Operation completed without errors."
        

        
    def find(self, key, similarity = '', tolerance = 0.0):
        args = {'sim_name':similarity, 'tolerance':tolerance, 'data':key, 'platform':self.platform.getCPUInfo()}
        args['platform']['type'] = 'CPU'
        args = mangle(args)
        response = self.send_http(args)
        self.response = '%s.response.xml' % self.specname
        f = open(self.response, 'w')
        for line in response.readlines():
            f.write(line)
        f.close()
        rtree = xml.etree.ElementTree.ElementTree(file = open(self.response, 'r'))
        info = rtree.getroot().find('info')
        if len(info) > 0:
            print "Operation completed with errors:"
            for key in map(XMLWrapper, info):
                print key['reason']
        else:
            print "Operation completed without errors."
            
        self.records = map(XMLWrapper, rtree.getroot().find('results'))
        return self.records
        pass
                
    
        # platformname, platform, problem, results
    def update(self, data):
        args = {'op':'update','data':data, 'platform':self.platform.getCPUInfo()}
        #this is a temporary hack, something else should happen once GPU detection is available
        args['platform']['type'] = 'CPU'
        args = mangle(args)
        response = self.send_http(args, post = True)
        rtree = xml.etree.ElementTree.ElementTree(file = response)
        info = rtree.getroot().find('info')
        if len(info) > 0:
            print "Operation completed with errors:"
            for sub in map(XMLWrapper, info):
                print sub['reason']
        else:
            print "Operation completed without errors."
        
    def shutdown(self):
        pass
    def get_records(self):
        return self.records


type2prefix = {
            int:'i_',
            float:'f_',
            str:'s_',
            dict:'d_',
            list:'l_',
            long:'L_'
            }
str2type = {
            'int':int,
            'float':float,
            'str':str,
            'long':long
            }



def mangle(data):
    if type(data) is list:
        return map(lambda item: type2prefix[type(item)]+str(item), data)
    if type(data) is not dict:
        return data
    ret = {}
    for item in data.iteritems():
        ret[type2prefix[type(item[1])] + item[0]] = mangle(item[1])
    return ret


def pick_host(hosts = []):
    if len(hosts) is 0:
        with open('asp.ini') as hostlist:
            hosts.extend(hostlist.readlines())
    return hosts.pop()