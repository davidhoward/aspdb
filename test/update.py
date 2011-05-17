'''
Created on May 16, 2011

@author: david
'''
import random
import client.asp_client as asp_client


randwords = ['foo','bar','baz','garply']
trials = [{'foo':random.randrange(10), 'bar':random.random(), 'baz':random.choice(randwords)} for i in xrange(100)]

ac = asp_client.ClientDB('super')
for trial in trials:
    ac.update(trial)

ac.shutdown()