import struct
from asp.util import *
import pickle
import sys
import StringIO


#
class ASPCommandPipe(pickle.Unpickler):
    PICKLE_SAFE = {
        'marshaller': set(['Command','DisconnectCommand', 'FindCommand', 'HandShakeCommand', 'RecommendCommand', 'RegisterCommand', 'UpdateCommand']),
        '__builtin__':set(['bool','int', 'float', 'long', 'None', 'object', 'complex', 'str', 'list', 'tuple', 'type']),
        'collections': set(['dict']),
        'sqlite3': set(['Row']),
        'copy_reg':set(['_reconstructor'])
    }
    def find_class(self, module, name):
        if not module in self.PICKLE_SAFE:
            raise pickle.UnpicklingError(
                'Attempting to unpickle unsafe module %s' % module
            )
        __import__(module)
        mod = sys.modules[module]
        if not name in self.PICKLE_SAFE[module]:
            raise pickle.UnpicklingError(
                'Attempting to unpickle unsafe class %s' % name
            )
        klass = getattr(mod, name)
        return klass
 
    @classmethod
    def loads(cls, pickle_string):
        return cls(StringIO.StringIO(pickle_string)).load()

class Command(object):
    def __init__(self):
        self.data = {}
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, item):
        self.data[key] = item

        

def getCommand(sock):

    """
    Constructs a command object from the data in buff.


    Translate assumes that buff is nonempty.
    If more than the specified amount of data exists, Translate
    will truncate the buffer and leave the unread data inside.
    If insufficient data exists to create the command, Translate
    will raise an IndexError.
     If the command code (first byte) of the command is not recognized, a KeyError will be raised.
     A ValueError is raised if any size field holds an illegal
    value.
    """
    #get the buff; block until we have it all
    try:
        take = 2
        buff = sock.recv(take)
        #debug_print('Received command from %s at port %s' % sock.getpeername())
        #debug_print('Received command was %s' % map(ord,buff))
    
        size = struct.unpack_from('>H', buff, 0)[0]
        #debug_print('Demarshalled size as %d' % size)

        #debug_print('Taking %d bytes of data' % take)
        cbuff = sock.recv(size)
    #get the appropriate subclass and construct
        cmd = ASPCommandPipe.loads(cbuff)
    #debug_print('Determined subclass as %s' % subclass)
        return cmd
    except Exception as e:
        print "Demarshalling error: %s" %  e.message
        print "Connection terminated."
        return InvalidCommand()

def write_command(cmd, sock):
    cstring = pickle.dumps(cmd)
    size = len(cstring)
    sock.send(struct.pack('>H',size))
    sock.send(cstring)
        
def extract_bytes(i):
    b = bytearray(4)
    if type(i) is float:
        struct.pack_into('!f', b, 0, i)
    elif type(i) is int:
        struct.pack_into('!i', b, 0, i)
    return b
  
  #extract multiple big-endian 32 bit integers
def extract_ints(buff, offset = 0, num = 1):
    b = buffer(buff)
    return [ struct.unpack_from('!i', b, offset+4*i)[0] for i in xrange(num)]

def extract_floats(buff, offset = 0, num = 1):
    b = buffer(buff)
    return [ struct.unpack_from('!f', b, offset + 4*i)[0] for i in xrange(num)]
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



class DisconnectCommand(object):
        pass
        
class FindCommand:
    #modes
    QUERY = 0
    WAITING = 1
    FINISHED = 2
    def __init__(self, **kwargs):
        self.data = {}
        if 'mode' in kwargs:
            self['mode'] = kwargs['mode']
            self['reason'] = kwargs.setdefault('reason', "")
        else:
            #this is a query
            self['mode'] = self.QUERY
            self['platform'] = kwargs['platform']
            self['key'] = kwargs['key']
            self['tolerance'] = kwargs['tolerance']
          
    def __setitem__(self, key, val):
        self.data[key] = val
    def __getitem__(self, key):
        return self.data[key]

class HandShakeCommand:
    ACCEPTED = 1
    DROPPED = 0
    NAME_INVALID = 2
    REJECTED = 4
    
    #modes
    ACK = 0
    READ = 16
    ADMINISTRATOR = 32
    READ_WRITE = 48
    
    
    def __init__(self, **kwargs ):
        #kwargs keys: specname, name, password, strateng
        self.data = {}
        for key in ['specname', 'name', 'password', 'strateng', 'reason', 'ret']:
            if key in kwargs:
                self.data[key] = kwargs.setdefault(key,None)
        self.mode = 0
        if self['specname']:
            self.mode |= self.READ
        if self['name'] and self['password']:
            self.mode |= self.ADMINISTRATOR
        if self['ret']:
            self.mode = self.ACK
                
    def __getitem__(self, key):
        try:
            return self.data[key]
        except KeyError:
            return None
        
                        
class InvalidCommand(object):
    def __getitem__(self, key):
        return None
class RecommendCommand:

    def __init__(self, buff = None, platform = None, problem = None):
        self.ack = False
        if buff:
            sizes = (buff[1], buff[2])
            offset = 3
            self.platform = [ buff[offset+i] for i in range(sizes[0])]
            offset += sizes[0]
            self.problem = [ buff[offset+i] for i in range(sizes[1])]
        else:
            self.platform = platform
            self.problem = problem
    @staticmethod
    def ack():
        ret = RecommendCommand()
        ret.ack = True
        return ret

    def marshall(self):
        m = bytearray((4,0,0))
        if self.ack:
            m[0] = -2
            return m
        index = 0
        for vector in (self.platform, self.problem):
            index += 1
            if vector:
                m[index] = len(vector)
                for entry in vector:
                    m.extend(extract_bytes(entry))
    def get_results(self):
        return self.platform

class RegisterCommand:
    
    #mode stuff
    SUCCESS = 1
    NAME_INVALID = 2
    PERMISSION_DENIED = 4
    REGISTER = 16
    UPDATE = 32
    
    #URPS
    SET_URP_DONT = 0
    SET_URP_ON = 1
    SET_URP_OFF = -1
    
    def __init__(self, **kwargs):
        self.data = {}
                
        for key in ['specname', 'name', 'password']:
            self.data[key] = kwargs.setdefault(key,None)    
        
        
        if 'mode' in kwargs:
            self.data['mode'] = kwargs['mode']
            self.data['reason'] = kwargs.setdefault('reason',"")
            self.data['specname'] = None
        elif 'key_structure' in kwargs:
            # registering a new specialiser
            self.data['key_structure'] = kwargs['key_structure']
            self.data['mode'] = self.REGISTER
        else:
            #updating a specialiser.
            self.data['mode'] = self.UPDATE
            self.data['addFields'] = kwargs.setdefault('addFields', None)
            self.data['setURP'] = kwargs.setdefault('setURP', None)
    
    def __getitem__(self, key):
        return self.data['key']
    

class UpdateCommand(object):
    #This is command is carrying actual run data
    LOADED = 0
    #Ack for a succssful update
    ACCEPTED = 1
    #query was malformed, or needed owner status but didnt have it
    REJECTED = 2
    
    def __init__(self, **kwargs):
        if 'retcode' in kwargs:
            self.retcode = kwargs['retcode']
            if 'reason' in kwargs:
                self.reason = kwargs['reason']
        else:
            try:
                self.platform = kwargs['platform']
                self.problem = kwargs['problem']
                self.results = kwargs['results']
            except KeyError:
                raise ValueError('Update must specify a valid platform, problem, and result dictionary')
                    
                     
                
            
            
subs = {
        0:HandShakeCommand,
        1:FindCommand,
        2:UpdateCommand,
        4:RecommendCommand,
        14:RegisterCommand,
        28:DisconnectCommand
        
        }
MAX_PACKET_SIZE = 2**16 - 1
known_platforms = { 'cpu':5, 'manycore':4}
