import sqlite3
from dbconfig import *
from marshaller import *
import sys



#required methods for DB:
# recommend
# query
# update

platform_ids = { 1:'cpu', 2:'gpu' }
plus = lambda a,b: a+b


class ASPDB:

    def __init__(self, specname):
        self.conn = sqlite3.connect('%s/%s' % (ASPHOME, DB_FOR_SPECIALISER(specname)))
        self.conn.row_factory = sqlite3.Row
        self.specname = specname
       
    def shutdown(self):
        self.conn.close()

    def find(self, platform, key, tolerance = 0.0):
        # create the sample
        c = self.conn.cursor()
        c.execute('select * from primary_runs where platform_type = ?', platform.getType())
        return filter(lambda result: self.similarity(key, result) >= tolerance, c.fetchall())
        # conform records to pattern, filter
        #return the bunch for sending back
   
   
    def update(self, platform, key):
        cursor = self.conn.cursor()

        s_key, s_val = db_format_inputs(platform, key)
        cursor.execute("insert into primary_runs %s values%s;" % (s_key, s_val))
        run = cursor.lastrowid

        plat_record = platform.format_record(run)
        cursor.execute("insert into %s values %s" % (PLATFORM_TABLE_NAME(platform.getType())), plat_record)
        
        self.conn.commit()
        
    
    def similarity(self, record, sample):
        return 1.0
        
        

                # otherwise the values are considered wholely dissimilar. might want to change this later.

def sqlite_empty_record(size, wildcard = '?'):
    ret = "(" + reduce(plus, ["%s," % wildcard for i in xrange(size)])
    ret = ret[:len(ret) - 1]
    ret += ")"
    return ret
    
def dot(v1, v2):
    return float (reduce(plus, map(plus, v1, v2)))



def check_structure(s):
        numerics = [int, float, long]
        try:
            for item in s:
                if not (check_name_valid(item[0]) and item[1] in numerics and type(item[2]) is item[1]): return False
            return True
        except Exception:
            return False
def db_format_inputs(platform, key):
    size = len(key) + 1
    s_keys = ('platform',)
    s_vals = ("'%s'" % platform.getArchType(),)
    for kv in key.iteritems():
        s_keys.append(kv[0])
        val = kv[1]
        if type(val) is str:
            val = "'%s'" % val
        s_vals.append(val)
        
    s_key = sqlite_empty_record(size, wildcard = '%s') % s_keys
    s_val = sqlite_empty_record(size, wildcard = '%s') % s_vals
    return s_key, s_val

def register_specialiser(specname, name, password, key_structure):
    if not check_name_valid(specname):
        raise ValueError('New Specialisers must specify a valid specailiser name')
    if not check_name_valid(name):
        raise ValueError('New Specialisers must specify a valid owner name')
    if not check_name_valid(password):
        raise ValueError('New Specialisers must specify a valid password')
    if not check_structure(key_structure):
        raise ValueError('New Specialisers must specify a valid key structure')
    
    
    registry = sqlite3.connect(REGISTRY_DB)
        
    #Attempt to add specialiser to the registry.
    try:
        registry.execute('insert into owners (specname, name, password) values (?,?,?)', (specname, name, password))
        registry.commit()
    except sqlite3.IntegrityError:
        registry.close()
        raise ValueError('Specialiser name was invalid or already in use.' )
    
    #Attempt to Create the database file and set up the internal structure.
    try:
        new_spec = sqlite3.connect('%s/%s.spec.db' % (ASPHOME, specname))
        t_struct = generate_sql_table_structure(key_structure)
        t_rest = t_struct[1:]
        t_struct = '( run int PRIMARY KEY, platform_type text, ' + t_rest
        new_spec.execute('create table primary_runs %s' % t_struct)
        for recipie in platform_table_recipies:
            new_spec.execute(recipie)
        new_spec.commit()
        new_spec.close()
    except Exception as e:
        os.remove('%s/%s.spec.db' % (ASPHOME, specname))
        registry.execute('delete from owners where specname = ?', (specname,))
        registry.commit()
        registry.close()
        raise e
        
def modify_specialiser(specname, name, password, **kwargs):
    if not check_name_valid(specname):
        raise ValueError('Unknown specialiser: %s' % specname)
    if not check_name_valid(name):
        raise ValueError('Malformed owner name: %s' % name)
    if not check_name_valid(password):
        raise ValueError('Malformed password: %s' % password)
    
    registry = sqlite3.connect(REGISTRY_DB)
    c = registry.cursor()
    c.execute('Select count(*) from owners where specname = ?, name = ?, password = ?', (specname, name, password))
    count = c.fetchone()[0]
    if not count:
        registry.close()
        raise Exception('Owner name/password did not match; Permission to modify specialiser denied.')
    
    if 'addFields' in kwargs:
        fields = kwargs['addFields']
        if type(fields) is tuple:
            fields = [fields]
        if not check_structure(fields):
            raise ValueError('Invalid key structure for new field(s).')
        spec = sqlite3.connect(DB_FOR_SPECIALISER(specname))
        for field in fields:
            spec.execute('alter table primary_runs add column %s %s default %s' % (field[0], type_strings[field[1]], field[2]))
        spec.commit()
        spec.close()
    if 'setURP' in kwargs:
        if not type(kwargs['setURP']) is int:
            raise ValueError('Update-Requires-Permission must be an integer value.')
        registry = sqlite3.connect(REGISTRY_DB)
        registry.execute('update owners set URP = ? where specname = ?', (kwargs['setURP'], specname))
        
        
def get_similarity(f_mod, f_name):
    checker  = sqlite3.connect(REGISTRY_DB)
    c = checker.cursor()
    c.execute('select permitted from sim_functions where module = ? and func = ?;', (f_mod, f_name))
    permitted = c.fetchone()[0]
    if permitted:
        return getattr(sys.modules[f_mod], f_name)
    else:
        return None