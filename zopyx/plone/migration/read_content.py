""" 
Read a pickle file and pretty-print its content
"""

import sys
import pprint 
import cPickle

def read_pickle(pck_name):
    pprint.pprint(cPickle.load(open(pck_name)))

if __name__ == '__main__':
    read_pickle(sys.argv[1])
