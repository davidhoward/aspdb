import client.asp_client as asp_client
import sys

name = 'zzz'
if sys.argv[1]:
    name = sys.argv[1]
    
ac = asp_client.ClientDB(name)
ks = {'foo':1, 'bar':1, 'angle':.25}
ac.register_specialiser(specname = name, key_structure = ks)

ac.shutdown()

