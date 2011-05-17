'''
Created on Apr 8, 2011

@author: david
'''
import sqlite3

ASP_port = 0xadb
ASP_HOST = ""
MAX_USERS = 20
ASPHOME = "/home/ASP"
hostlist = [
            ("", 0xadb)
            
            
            ]
### Specialiser DB conventions
PRIMARY_TABLE_NAME = 'primary_runs'
RESULT_TABLE_NAME = 'results'
PLATFORM_TABLE_NAME = lambda platform: 'platform_%s' % platform
DB_FOR_SPECIALISER = lambda spec : '%s.spec.db' % spec
REGISTRY_DB = "%s/registry.db" % ASPHOME

type_strings = {
                int:'int',
                str:'text',
                long: 'int',
                float: 'real',
                
                                
                }

platform_table_recipies = [
                   'create table platform_cpu (run int PRIMARY KEY, vendorID text, cpuFamily int, numCores int, model int, cacheSize int)',
                   'create table platform_gpu (run int PRIMARY KEY)'
                   ]

def generate_sql_table_structure(structure):
    fields = map(lambda kv: '"%s"' % kv[0] + " " + type_strings[kv[1]] + " DEFAULT %s" % kv[2], structure)
    fields = reduce(lambda f1, f2: f1 + ", " + f2, fields)
    return "(%s)" % fields
        
def generate_sql_insert_structure(structure):
    fields = structure.iterkeys()
    vals = map( str, structure.itervalues())
    fields = reduce(lambda f1, f2: f1 + ", " + f2, fields)
    vals = reduce( lambda v1, v2: v1 + ", " + v2, vals)
    return "(%s)" % fields, "(%s)" % vals

if __name__ == '__main__':
    print 'about to connect'
    dbname = '%s/registry.db' % ASPHOME
    print 'dbname = ', dbname
    conn = sqlite3.connect(dbname)
    c = conn.cursor()
    c.executescript('''drop table admins;
                     drop table owners;
                ''');
    c.execute('create table admins (name text, password text, UNIQUE(name, password))')
    # create the ownership table. urp = Update Requires Permission.
    c.execute('create table owners (specname text PRIMARY KEY , probsize int, ressize int, name text, password text, URP int DEFAULT 0)')
    print 'about to commit'
    conn.commit()
    c.close()
    conn.close()