'''
Created on May 17, 2011

@author: david
'''

import client.asp_client as asp_client

ac = asp_client.ClientDB('super')
sample = {'foo':2, 'baz':'hello', 'garply':7.0}
ac.find(sample, similarity = 'g.h', tolerance = 0.34)

for result in ac.records:
    print 'bar = ' + str(result['bar'])
