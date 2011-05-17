'''
Created on May 8, 2011

@author: david
'''
import xml.etree.ElementTree
type_strings = {
                int:'int',
                str:'str',
                float: 'float',
                type:'type',
                long:'long'              
                                
                }

string2type ={
              'int':int,
              'string':str,
              'float':float,
              'long':long
              }
validchars = ['.', '-','_']

def check_name_valid(name):
    try:
        if len(name) < 3 or len(name) > 30:
            return False
        for char in name:
            if not char.isalnum() and not char in validchars:
                return False
        return True
    except Exception:
        return False
    
    
def check_structure(s):
        numerics = [int, float, long]
        try:
            for item in s:
                if not (check_name_valid(item[0]) and item[1] in numerics and type(item[2]) is item[1]): return False
            return True
        except Exception:
            return False
        
        
def read_key_structure(request):
    return []

def format_field(name, typ, default):
    
    pass

def auth_owner(specname, name, password):
    pass

def interleave(password, salt):
    ret = bytearray()
    for i in xrange(len(password)):
        ret.append(password[i])
        ret.append(salt[i])
    return str(ret)

def flatten(d):
    ret = {}
    for key in d:
        ret[key] = d[key][0]
    return ret



def demarshall_record(record_line):
    props = record_line.split()
    ret = {}
    for prop in props:
        stuff = prop.split(',')
        ret[stuff[0]] = string2type[stuff[1]](stuff[2])
    return ret

def dictToXML(d, name = 'base'):
    """
    Converts a flat dictionary to a serializeable ElementTree representation.
    
    The ElementTree module will not serialize certain basic types, such as int.
    This method exists to losslesly represent a dictionary of such types in a way
    which can be serialized with ElementTree's faculties.
    """
    e_base = xml.etree.ElementTree.Element(name)
    for kv in d:
        e_base.append(xml.etree.ElementTree.Element(kv, {'type':type_strings[type(d[kv])], 'val':str(d[kv])}))
    return e_base

plus = lambda a,b:a+b
times = lambda a,b:a*b
def dot(v_1, v_2):
    return reduce(plus, map(times, v_1, v_2))