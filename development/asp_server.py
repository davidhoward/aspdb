'''
Created on Apr 25, 2011

@author: david
'''
import SocketServer
import argparse
from marshaller import *
from dbconfig import *
import aspDB
import StrategyEngine

plus = aspDB.plus

class DBServer(SocketServer.ForkingMixIn, SocketServer.TCPServer): pass

class ASPDBRequestHandler(SocketServer.StreamRequestHandler):
    
    def exec_disconnect(self, cmd):
        self.active = False
        if(self.db):
            self.db.shutdown()
        self.send( DisconnectCommand() )
        
    def exec_find(self, cmd):
        remaining = [ self.db.find(cmd['platform'], cmd['key'], cmd['tolerance'])]
        while len(remaining) > 0:
            pick = remaining.pop()
            rs = pickle.dumps(pick)
            if len(rs) > MAX_PACKET_SIZE:
                half = len(pick)/2
                remaining.append(pick[:half])
                remaining.append(pick[half:])
            else:
                self.send(pick)
        self.send( FindCommand( mode = FindCommand.FINISHED, reason = 'Transmission complete.'))
    def exec_register(self, cmd):
        if not check_name_valid(cmd['specname']):
            self.send( RegisterCommand( opts = RegisterCommand.NAME_INVALID, reason = 'Malformed specialiser name' ))
        #determine the nature of the operation; Definition or owner registration?
        #process the definition first if present, then the owner registration.
        response = None
        if cmd['mode'] is RegisterCommand.REGISTER:
            if self.admin:
                try:
                    aspDB.register_specialiser(cmd['specname'], cmd['name'], cmd['password'], cmd['key_structure'])
                    response = RegisterCommand( mode = RegisterCommand.SUCCESS, reason = 'Registratrion Successful')
                except Exception as e:
                    response = RegisterCommand( mode = RegisterCommand.NAME_INVALID, reason = e.args)
            else:
                response = RegisterCommand( mode = RegisterCommand.PERMISSION_DENIED, reason = 'Administrator permissions required to register a new specialiser.')
        elif cmd['mode'] is RegisterCommand.UPDATE:
            print "Registering update"
            if cmd['addFields']:
                print "Registering addFields"
                try:
                    aspDB.modify_specialiser(specname = cmd['specname'], name = cmd['name'], password = cmd['password'], addFields = cmd['addFields'] )
                    response = RegisterCommand( mode = RegisterCommand.SUCCESS, reason = 'Specialiser Update Successful')
                except Exception as e:
                    response = RegisterCommand( mode = RegisterCommand.NAME_INVALID, reason = e.args)
            if cmd['setURP'] and (response is None or response.mode == RegisterCommand.SUCCESS):
                print "Registering URP"
                try:
                    aspDB.modify_specialiser(specname = cmd['specname'], name = cmd['name'], password = cmd['password'], setURP = cmd['setURP'])
                    response = RegisterCommand( mode = RegisterCommand.SUCCESS, reason = 'Specialiser Update SUccessful')
                except Exception as e:
                    response = RegisterCommand( mode = RegisterCommand.NAME_INVALID, reason = e.args)
        if response is None:
            response = RegisterCommand( mode = RegisterCommand.NAME_INVALID, reason = 'No valid arguments detected')
        #if we haven't returned by this point, something just wasnt right.
        self.send(response)
        
            
    def exec_update(self, cmd):
            #check if we have appropriate permission
            if not self.db:
                debug_print('rejecting update; db not initialised')
                self.send( UpdateCommand( opts = UpdateCommand.REJECTED ))
                return
            if not self.canupdate:
                if self.owner:
                    self.canupdate = True
                else:
                    checker = sqlite3.connect('%s/registry.db' % ASPHOME)
                    c = checker.cursor()
                    c.execute('select URP from owners where specname = ?', (self.db.specname,))
                    urp = c.fetchone()[0]
                    if urp:
                        checker.close()
                        debug_print('rejecting update; higher permissions needed')
                        self.send( UpdateCommand( opts = UpdateCommand.REJECTED))
                        return
                    checker.close()
                    
            #update
            try:
            # debug_print('problem type: %s' % type(cmd.problem))
                self.db.update(cmd.platform_name, cmd.platform, cmd.problem, cmd.results)
                self.send( UpdateCommand( opts = UpdateCommand.ACCEPTED))
            except Exception:
                #debug_print(e.message)
                self.send( UpdateCommand(opts = UpdateCommand.REJECTED))
        
    def exec_handshake(self, cmd):
        #this command should also contain information about the specialiser
        #with which we are dealing.
        debug_print('Server thread %d received handshake' % os.getpid())
        if cmd.mode == HandShakeCommand.ADMINISTRATOR:
            if not (check_name_valid(cmd['name']) and check_name_valid(cmd['password'])):
                self.send(HandShakeCommand( ret = HandShakeCommand.REJECTED, reason = 'Administrator name or password invalid'))
                return
            checker = sqlite3.connect('%s/registry.db' % ASPHOME)
            c = checker.cursor()
            c.execute('select count(*) from admins where name = ? and password = ?', (cmd['name'], cmd['password']))
            count = c.fetchone()[0]
            if not count > 0:
                self.send(HandShakeCommand( ret = HandShakeCommand.REJECTED, reason = 'Administrator name/password did not match'))
            else:
                self.admin = True
                self.send(HandShakeCommand( ret = HandShakeCommand.ACCEPTED))
            checker.close()
            
        elif cmd.mode == HandShakeCommand.READ:
            specname = cmd['specname']
            if not check_name_valid(specname):
                self.send(HandShakeCommand( ret = HandShakeCommand.NAME_INVALID ))
                return
            checker = sqlite3.connect('%s/registry.db' % ASPHOME)
            c = checker.cursor()
            c.execute('select count(*) from owners where specname = ?', (specname,))
            count = c.fetchone()[0]
            if not count > 0:
                self.send(HandShakeCommand( ret = HandShakeCommand.NAME_INVALID, reason = 'Unknown specialiser'))
            else:
                self.specname = specname
                response = self.init_db(specname, cmd['strateng'])
                self.send(HandShakeCommand( ret = HandShakeCommand.ACCEPTED, reason = response))
                self.owner, self.canupdate = False, False
            checker.close()
            
        elif cmd.mode == HandShakeCommand.READ_WRITE:
            specname = cmd['specname']
            if not check_name_valid(specname):
                self.send( HandShakeCommand( ret = HandShakeCommand.NAME_INVALID, reason = 'Invalid specialiser name' ))
                return
            elif not (check_name_valid(cmd['name']) and check_name_valid(cmd['password'])):
                self.send( HandShakeCommand( ret = HandShakeCommand.REJECTED, reason = 'Invalid owner name or password' ))
                return
            checker = sqlite3.connect('%s/registry.db' % ASPHOME)
            c = checker.cursor()
            c.execute('select count(*) from owners where specname = ? and name = ? and password = ?', (specname, cmd['name'], cmd['password']))
            count = c.fetchone()[0]
            if not count:
                checker.close()
                self.send( HandShakeCommand( ret = HandShakeCommand.REJECTED, reason = 'Owner name/password did not match for desired specialiser'))
                return
            self.owner, self.canupdate = True, True
            self.specname = specname
            self.init_db(specname, cmd['strateng'])
            self.send( HandShakeCommand(ret = HandShakeCommand.ACCEPTED))
        
    def init_db(self, specname, strateng = None):
        if self.db :
            self.db.shutdown()
        self.db = aspDB.ASPDB(self.specname)
        #figure out some way to do this biusiness...
        return ""
    
    def setup(self):
        self.ops = { RegisterCommand:self.exec_register,
                     HandShakeCommand:self.exec_handshake,
                     UpdateCommand:self.exec_update,
                     DisconnectCommand:self.exec_disconnect,
                     FindCommand:self.exec_find
                    }
    def handle(self):
        #remain latent until handshake command is sent
        debug_print('Connection request received from %s at port %s' % self.request.getpeername())
        self.current = None
        self.admin = False
        self.owner = False
        self.canupdate = False
        self.db = None
        self.send(HandShakeCommand(ret = HandShakeCommand.ACCEPTED))
        self.active = True

        while self.active:
            current = getCommand(self.request)
            try:
                debug_print('Preparing to execute command %s' % current)
                if current.__class__ is InvalidCommand:
                    break
                exe = self.ops[current.__class__]
                exe(current)
            except KeyError:
                print 'Functionality for %s not implemented' % current.__class__
            
                  
        #Translate into an ASPDB command
        #verify this command, if necessary
        #execute the command with command.execute(self.request)
        
    
    def send(self, cmd):
        write_command(cmd, self.request)

### stuff pertaining to authentication
admins = dict()
owners = dict()

if __name__ == '__main__':
    # get args from command line
    parser = argparse.ArgumentParser(description = "ASP-SEJITS Database Server.")
    parser.add_argument('-u',nargs = 2,type = str, help = "Specify an administrator name and password for this server. First argument should be the name, followed by the password.")
    args = parser.parse_args()
    
    
    if args.u:
        name = args.u[0]
        passw = args.u[1]
        admins = sqlite3.connect('%s/registry.db' % ASPHOME)
        c = admins.cursor()
        try:
            c.execute('insert into admins values(?,?)', (name, passw))
            admins.commit()
        except sqlite3.IntegrityError:
            print 'Administrator name/password combination already registered; Ignoring.'
        admins.close()
        
    serv = DBServer((ASP_HOST, ASP_port), ASPDBRequestHandler)
    serv.request_queue_size = 20
    serv.serve_forever()

    