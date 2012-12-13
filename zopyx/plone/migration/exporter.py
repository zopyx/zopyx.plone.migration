################################################################
# Plone ini-style exporter
#
# Written by Andreas Jung
# (C) 2008, ZOPYX Ltd. & Co. KG, D-72070 Tuebingen
################################################################

import os
import gc
import shutil
import tempfile
import cPickle

IGNORED_TYPES = (
    'NewsletterTheme',
)

def export_groups(options):

    log('Exporting groups')
    fp = file(os.path.join(options.export_directory, 'groups.ini'), 'w')

    acl_users = options.plone.acl_users
    for i, group in enumerate(acl_users.source_groups.getGroups()):
        print >>fp, '[%d]' % i
        print >>fp, 'name = %s' % group.getId()
        print >>fp, 'members = %s' % ','.join(group.getMemberIds())
        print >>fp, 'roles = %s' % ','.join(group.getRoles())

    fp.close()
    log('exported %d groups' % len(acl_users.source_groups.getGroups()))

def export_members(options):

    log('Exporting Members')
    fp = file(os.path.join(options.export_directory, 'members.ini'), 'w')

    acl_users = options.plone.acl_users
    pm = options.plone.portal_membership

    try:
        # Plone 2.5
        passwords = options.plone.acl_users.source_users._user_passwords
    except:
        # Plone 2.1
        passwords = None

    for username in acl_users.getUserNames():
        user = acl_users.getUserById(username)
        member = pm.getMemberById(username)
        if member is None:
            continue
        roles = [r for r in member.getRoles() if not r in ('Member', 'Authenticated')]
        print >>fp, '[member-%s]' % username
        print >>fp, 'username = %s' % username
        if passwords:
            print >>fp, 'password = %s' % passwords.get(username)
        else:
            try:
                print >>fp, 'password = %s' % user.__
            except AttributeError:
                print >>fp, 'password = %s' % 'n/a'

        print >>fp, 'fullname = %s' % member.getProperty('fullname')
        print >>fp, 'email = %s' % member.getProperty('email')
        print >>fp, 'roles = %s' % ','.join(roles) 
        print >>fp
    fp.close()
    log('exported %d users' % len(acl_users.getUserNames()))

def log(s):
    print >>sys.stdout, s

def _getReviewState(obj):
    try:
        return obj.portal_workflow.getInfoFor(obj, 'review_state')
    except WorkflowException:
        print 'error review state'
        return None

def _getTextFormat(obj):
    text_format = None
    if hasattr(obj, 'text_format'):
        text_format = obj.text_format
    return text_format

def _getContentType(obj):
    text_format = _getTextFormat(obj)
    ct = None       
    try:
        ct = obj.getContentType()
    except AttributeError:
        ct = obj.content_type()
    if ct is not None: 
        if text_format in ('html', 'structured-text'):
            ct = 'text/html'
    return ct

def _getParents(obj):
    result = list()
    current = obj
    while current.portal_type != 'Plone Site':
        result.append(dict(id=current.getId(), portal_type=current.portal_type))
        current = current.aq_inner.aq_parent
    return list(reversed(result))


def _getRelativePath(obj, plone):
    plone_path = '/'.join(plone.getPhysicalPath())
    obj_path = '/'.join(obj.getPhysicalPath())
    return obj_path.replace(plone_path + '/', '')

def export_content(options):

    log('Exporting content')
    catalog = options.plone.portal_catalog
    export_dir = os.path.join(options.export_directory, 'content')
    os.mkdir(export_dir)
    brains = catalog()
    log('%d items' % len(brains))

    fp = file(os.path.join(options.export_directory, 'content.ini'), 'w')
    errors = list()
    num_exported = 0
    stats = dict()
    for i, brain in enumerate(brains):
    
        if options.verbose and i % 50 == 0:
            log(i)
        try:
            obj = brain.getObject()
        except Exception, e:
            try:
                obj = options.plone.unrestrictedTraverse(brain.getPath())
            except Exception, e:
                errors.append(dict(path=brain.getPath(), error=e))
                continue
            
        try:
            schema = obj.Schema()
        except AttributeError:
            errors.append(dict(path=brain.getPath(), error='no schema'))
            continue

        if obj.portal_type in IGNORED_TYPES:
            continue

        obj_data = dict(schemadata=dict(), metadata=dict())        
        ext_filename = None
        for field in schema.fields():
            name = field.getName()
            value = field.get(obj)
            if name in ('image', 'file'):
                ext_filename = os.path.join(export_dir, '%s.bin' % obj.UID())
                extfp = file(ext_filename, 'wb')
                extfp.write(str(value))
                extfp.close()
                value = 'file://%s.bin' % obj.UID()
            elif name == 'relatedItems':
                value = [obj.UID() for obj in value]
            obj_data['schemadata'][name] = value

        obj_data['metadata']['uid'] = obj.UID()
        obj_data['metadata']['portal_type'] = obj.portal_type
        obj_data['metadata']['review_state'] = _getReviewState(obj)
        obj_data['metadata']['owner'] = obj.getOwner().getUserName()
        obj_data['metadata']['content_type'] = _getContentType(obj)
        obj_data['metadata']['text_format '] = _getTextFormat(obj)
        obj_data['metadata']['local_roles'] = obj.get_local_roles()
        obj_data['metadata']['parents'] = _getParents(obj)
        obj_data['metadata']['path'] = _getRelativePath(obj, options.plone)

        if not stats.has_key(obj.portal_type):
            stats[obj.portal_type] = 0
        stats[obj.portal_type] += 1
        num_exported += 1

        # write to INI file
        print >>fp, '[%d]' % i
        print >>fp, 'path = %s' % _getRelativePath(obj, options.plone)
        print >>fp, 'id = %s' % obj.getId()
        print >>fp, 'portal_type = %s' % obj.portal_type
        print >>fp, 'uid = %s' % obj.UID()
        print >>fp

        # dump data as pickle
        pickle_name = os.path.join(export_dir, obj.UID())
        cPickle.dump(obj_data, file(pickle_name, 'wb'))

    fp.close()

    if errors:
        log('Errors')    
        for e in errors:
            log(e)

    log('Stats')
    log('%d items exported' % num_exported)
    for k in sorted(stats.keys()):
        log('%-40s %d' % (k, stats[k]))


def migrate_site(app, options):

    plone = app.unrestrictedTraverse(options.path, None)
    if plone is None:
        raise RuntimeError('Plone site not found (%s)' % options.path)

    site_id = plone.getId()
    export_dir = os.path.join(options.output, site_id)
    if os.path.exists(export_dir):
        shutil.rmtree(export_dir, ignore_errors=True)
    os.makedirs(export_dir)

    log('Exporting Plone site: %s' % options.path)
    log('Export directory:  %s' % os.path.abspath(export_dir))

    app = Zope.app()
    uf = app.acl_users
    user = uf.getUser(options.username)
    if user is None:
        raise ValueError('Unknown user: %s' % options.username)
    newSecurityManager(None, user.__of__(uf))

    options.export_directory = export_dir
    options.plone = plone

    export_groups(options)
    export_members(options)
    export_content(options)
    log('Export done...releasing memory und Tschuessn')

if __name__ == '__main__':

    from optparse import OptionParser
    from AccessControl.SecurityManagement import newSecurityManager
    import Zope
    gc.enable()

    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-p', '--path', dest='path', default='')
    parser.add_option('-o', '--output', dest='output', default='')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      default=False)

    options, args = parser.parse_args()
    options.app = app
    migrate_site(app, options)
