################################################################
# Poor men's Plone export
# (C) 2012, ZOPYX Ltd, D-72074 Tuebingen
################################################################

import os
import shutil
import tempfile
import glob
import transaction
import urllib2
import cPickle
from optparse import OptionParser
from datetime import datetime
from ConfigParser import ConfigParser

from DateTime.DateTime import DateTime
from OFS.Folder import manage_addFolder
from Testing.makerequest import makerequest
from AccessControl.SecurityManagement import newSecurityManager


def fixup_plone(app, options):

    plone = app.restrictedTraverse(options.dest_site)
    

def fixup(options):

    uf = app.acl_users
    user = uf.getUser(options.username)
    if user is None:
        raise ValueError('Unknown user: %s' % options.username)
    newSecurityManager(None, user.__of__(uf))

    fixup_plone(app, options)
    log('Committing...')
    transaction.commit()
    log('done')
    log(url)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-s', '--dest-site', dest='dest_site', default=None)
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False)
    options, args = parser.parse_args()
    fixup(options)


