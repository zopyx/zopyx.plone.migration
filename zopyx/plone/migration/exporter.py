################################################################
# Poor men's Plone export
# (C) 2013, ZOPYX Ltd, D-72074 Tuebingen
################################################################

###################################################################################
# The purpose of this export script is to export AT-based content
# into a more generic format that can be used by an importer script
# for re-import into a Plone 4 site.
#
# Usage:
# bin/instance run exporter.py --path /path/to/<plone_id>--output <directory>
# 
# The exporter will create a self-contained directory with the exported
# data unter <directory>/<plone_id>. The directory will contain
# two INI files contents.ini and structure.ini  that describe
# the hierarchy structure of the exported site and exported contents.
# The metadata and real content of each object is stored within the 
# content subfolder. This directory will contain on file per exported
# content object. The filename is determined by the original UID
# of the content object. For binary files like File or Image there is
# a <uid>.bin file which will contain the original binary data.
# The files  (except the .bin files) are serialized using Python's
# Pickle mechanism in order to avoid serialization issues and to preserve
# the data as is.
# In addition the exporter cares out the export of members and groups
# (members.ini, groups.ini)
# 
# Tested with Plone 2.5, 3.3
###################################################################################

import os
import simplejson
import uuid
import gc
import shutil
import tempfile
import sys
import cPickle

from Acquisition import aq_base
from Acquisition import aq_inner
from Acquisition import aq_parent
from Testing.makerequest import makerequest
#from OFS.interfaces import IOrderedContainer
from Products.CMFCore.WorkflowCore import WorkflowException
from AccessControl.SecurityManagement import newSecurityManager

vcard_fields = [
 'academic',
 'bemerkung',
 'bundesland',
 'db_projekte',
 'expertise',
 'fachgebiete',
 'fon1',
 'fon2',
 'geburtstag',
 'geschlecht',
 'id',
 'institution',
 'institutsLocation',
 'kooperationsInteresse',
 'mitgliedschaften',
 'name',
 'plz',
 'position',
 'projekte',
 'title',
 'uniId',
 'uniName',
 'vorname',
]

IGNORED_TYPES = (
)


PT_REPLACEMENT = {
    'Large Plone Folder': 'Folder',
}


def log(s):
    print >>sys.stdout, s


def export_groups(options):
    """ Not working """
    return 
    log('Exporting groups')
    fp = file(os.path.join(options.export_directory, 'groups.ini'), 'w')

    md = options.plone.portal_memberdata
    gd = options.plone.portal_groupdata
    acl_users = options.plone.acl_users
    for i, group in enumerate(acl_users.Groups.acl_users.getUsers()):
        group_data = gd._members['group_' + group.getId()]
        
        print >>fp, '[%d]' % i
        print >>fp, 'name = %s' % group.getId()
        print >>fp, 'members = %s' % ','.join(group_data.getGroupMemberIds())
        print >>fp, 'roles = %s' % ','.join(group_data.getRoles())

    fp.close()
    log('exported groups')

def export_members(options):

    log('Exporting Members')
    fp = file(os.path.join(options.export_directory, 'members.ini'), 'w')
    fp = file(os.path.join(options.export_directory, 'members.ini'), 'w')

    acl_users = options.plone.acl_users
    members = options.plone.Members
    pm = options.plone.portal_membership

    try:
        # Plone 2.5
        passwords = options.plone.acl_users.source_users._user_passwords
    except:
        # Plone 2.1
        passwords = None

    for username in acl_users.getUserNames():
        if username.lower() == 'phols':
            import pdb; pdb.set_trace() 
        user = acl_users.getUserById(username)
        member = pm.getMemberById(username)
        membership = options.plone.portal_membership

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

        member_folder = members.get(username)
        vcard_data = dict()
        friends = []
        enemies = []
        if member_folder:

            if 'buddylist' in member_folder.objectIds():
                friends = member_folder.buddylist.confirmedBuddies.buddies
                enemies = member_folder.buddylist.blackListBuddies.buddies

            if 'photo' in member_folder.objectIds():
                try:
                    portrait_data = str(member_folder.photo)
                except AttributeError:
                    portrait_data = None
                if portrait_data:
                    portrait_fp = open(os.path.join(options.export_directory, 'member-portrait-%s.bin' % username), 'wb')
                    portrait_fp.write(portrait_data)
                    portrait_fp.close()
                    print >>fp, 'portrait_filename = eteaching/member-portrait-%s.bin' % username
                else:
                    print >>fp, 'portrait_filename = '

            if 'user' in member_folder.objectIds():
                vcard = member_folder['user']
                s = str(vcard)
                for name in vcard_fields:
                    vcard_data[name] = vcard.__dict__.get(name)
                    if name == 'geburtstag' and vcard_data[name]:
                        try:
                            vcard_data[name] = vcard_data[name].strftime('%02d.%02m.%4Y')
                        except ValueError:
                            vcard_data[name] = None
        print >>fp, 'vcard = %s' % simplejson.dumps(vcard_data)
        print >>fp, 'friends = %s' % simplejson.dumps(friends)
        print >>fp, 'enemies = %s' % simplejson.dumps(enemies)
        print >>fp

    fp.close()
    log('exported %d users' % len(acl_users.getUserNames()))


def newCounter():
    i = 0
    while 1:
        yield i
        i += 1


def export_structure(options):

    def _export_structure(fp, context, counter):
        if context.getId() == 'Members':
            return

        children = context.contentValues()
        children_uids = [_getUID(c) for c in children if _getUID(c)]
        context_uid = ''
        context_uid = _getUID(context)

        rel_path = _getRelativePath(context, options.plone)
        if rel_path in ['bawue']:
            continue

        print >>fp, '[%d]' % counter.next()
        print >>fp, 'id = %s' % context.getId()
        print >>fp, 'uid = %s' % context_uid
        print >>fp, 'path = %s' % rel_path
        print >>fp, 'portal_type = %s' % PT_REPLACEMENT.get(context.portal_type, context.portal_type)
        print >>fp, 'default_page = %s' % _getDefaultPage(context)
        print >>fp, 'children_uids = %s' % ','.join(children_uids)
        print >>fp, 'parent_position = %d' % _getPositionInParent(context)
        print >>fp, 'local_roles_block = %d' % _getLocalRolesBlock(context)
        print >>fp
        for child in children:
            if getattr(child.aq_inner, 'isPrincipiaFolderish', 0):
                _export_structure(fp, child, counter)

    log('Exporting structure')
    fp = file(os.path.join(options.export_directory, 'structure.ini'), 'w')
    _export_structure(fp, options.plone, newCounter())
    fp.close()    

def _getLocalRolesBlock(obj):
    val = getattr(obj, '__ac_local_roles_block__', 0) or 0 
    return int(val)

def _getReviewState(obj):
    try:
        return obj.portal_workflow.getInfoFor(obj, 'review_state')
    except WorkflowException:
#        log('Error retrieving review state for %s' % obj.absolute_url(1))
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
        try:
            ct = obj.getContentType()
        except TypeError:
            ct = obj.getContentType(obj)
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
        result.append(dict(id=current.getId(), 
                           portal_type=PT_REPLACEMENT.get(current.portal_type, current.portal_type)))
        current = current.aq_inner.aq_parent
    return list(result[::-1])


def _getRelativePath(obj, plone):
    plone_path = '/'.join(plone.getPhysicalPath())
    obj_path = '/'.join(obj.getPhysicalPath())
    return obj_path.replace(plone_path + '/', '')


def _getWFPolicy(obj):
    wf_policy = getattr(obj.aq_inner, '.wf_policy_config', None)
    if wf_policy is None:
        return {}
    if wf_policy.workflow_policy_below or wf_policy.workflow_policy_in:
        return wf_policy.__dict__
    return {}

def _getDefaultPage(obj):
    try:
        default_page = obj.getDefaultPage() or ''
    except AttributeError:
        default_page = getattr(obj.aq_inner.aq_base, 'default_page', '') 
    return default_page

def _getPositionInParent(obj):

    parent = aq_parent(aq_inner(obj))
    try:
        return parent.getObjectPosition(obj.getId())
    except:
        return 0

def _getUID(obj):
    try:
        return obj.aq_inner.aq_base.UID()
    except AttributeError:
        pass
        
    if hasattr(obj.aq_inner.aq_base, 'fake_uid'):
        return obj.aq_inner.fake_uid
    fake_uid = str(uuid.uuid4())
    obj.fake_uid = fake_uid
    return fake_uid

def export_placeful_workflow(options):
    if not 'portal_placeful_workflow' in options.plone.objectIds():
        return

    export_dir = os.path.join(options.export_directory, 'placeful_workflow')
    os.mkdir(export_dir)
    pwt = options.plone.portal_placeful_workflow
    for id_ in pwt.objectIds():
        zexp = pwt.manage_exportObject(id_, download=1)
        zexp_name = os.path.join(export_dir, id_ + '.zexp')
        file(zexp_name, 'wb').write(zexp)
        log('Exported PlacefulWorkflow %s to %s' % (id_, zexp_name))

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
    num_brains = len(brains)
    for i, brain in enumerate(brains):
        bin_count = 0

        if options.verbose:
            log('--> (%d/%d) %s' % (i, num_brains, brain.getPath()))
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
            schema = None
         
        if obj.portal_type in IGNORED_TYPES:
            continue

        path = brain.getPath()
        if 'Members/' in path:
            continue
            if '.trashcan' in path:
                continue
            if brain.getId in ('.personal', 'buddylist', 'linklists', 'messages', 'myevents', 'user'):
                continue

        obj_data = dict(schemadata=dict(), metadata=dict())        
        if schema:
            ext_filename = None
            for field in schema.fields():
                name = field.getName()   
                try:
                    value = field.get(obj)
                except Exception:#
                    value = str(getattr(obj, name, None))
                cls_ = str(field.__class__)
                if name in ('image', 'file', 'logo', 'themengrafik', 'datei', 'hp_foto', 'eteacher_foto') or 'ImageField' in cls_ or 'FileField' in cls_:
                    print name
                    bin_count += 1
                    ext_filename = os.path.join(export_dir, '%s-%d.bin' % (_getUID(obj), bin_count))
                    extfp = file(ext_filename, 'wb')
                    try:
                        data = str(value.data)
                    except:
                        data = value
                    if data:
                        extfp.write(data)
                    extfp.close()
                    value = 'file://%s/%s-%d.bin' % (os.path.abspath(export_dir), _getUID(obj), bin_count)
                elif name == 'relatedItems':
                    value = [_getUID(rel_item) for rel_item in value]
                obj_data['schemadata'][name] = value
        else:
            obj_data['schemadata']['title'] = obj.title
            obj_data['schemadata']['description'] = obj.description
            if obj.portal_type in ('Image', 'File'):
                bin_count += 1
                ext_filename = os.path.join(export_dir, '%s-%d.bin' % (_getUID(obj), bin_count))
                extfp = file(ext_filename, 'wb')
                extfp.write(str(obj.data))
                extfp.close()
                value = 'file://%s/%s-%d.bin' % (os.path.abspath(export_dir), _getUID(obj), bin_count)
                obj_data['schemadata'][obj.portal_type.lower()] = value
            elif obj.portal_type in ('Document',):
                obj_data['schemadata']['text'] = obj.text
                obj_data['schemadata']['content_type'] = obj.text_format
            elif obj.portal_type in ('Link',):
                # Dexterity Link type uses 'remoteUrl'
                obj_data['schemadata']['remoteUrl'] = obj.remote_url
            elif obj.portal_type in ('Event',):
                obj_data['schemadata']['start'] = obj.start_date
                obj_data['schemadata']['end'] = obj.end_date
                obj_data['schemadata']['contact_email'] = obj.contact_email
                obj_data['schemadata']['contact_name'] = obj.contact_name
                obj_data['schemadata']['contact_phone'] = obj.contact_phone
                obj_data['schemadata']['location'] = obj.location
                obj_data['schemadata']['event_url'] = obj.event_url
                try:
                    obj_data['schemadata']['timezone'] = obj.timezone
                except AttributeError:
                    obj_data['schemadata']['timezone'] = 'GMT+2'
                obj_data['schemadata']['subject'] = obj.subject
            print obj_data

        obj_data['metadata']['id'] = obj.getId()
        obj_data['metadata']['uid'] = _getUID(obj)
        obj_data['metadata']['portal_type'] = PT_REPLACEMENT.get(obj.portal_type, obj.portal_type)
        obj_data['metadata']['review_state'] = _getReviewState(obj)
        obj_data['metadata']['owner'] = obj.getOwner().getUserName()
        obj_data['metadata']['content_type'] = _getContentType(obj)
        obj_data['metadata']['text_format '] = _getTextFormat(obj)
        obj_data['metadata']['local_roles'] = obj.get_local_roles()
        obj_data['metadata']['parents'] = _getParents(obj)
        obj_data['metadata']['path'] = _getRelativePath(obj, options.plone)
        obj_data['metadata']['wf_policy'] = _getWFPolicy(obj)
        obj_data['metadata']['default_page'] = _getDefaultPage(obj)
        obj_data['metadata']['position_parent'] = _getPositionInParent(obj)
        obj_data['metadata']['local_roles_block'] = _getLocalRolesBlock(obj)
        obj_data['metadata']['modified'] = obj.modified()
        obj_data['metadata']['created'] = obj.created()

        if not stats.has_key(obj.portal_type):
            stats[obj.portal_type] = 0
        stats[obj.portal_type] += 1
        num_exported += 1
        
        try:
            related_items = ','.join([o.UID() for o in obj.getRelatedItems()])
            related_items_paths = ','.join([_getRelativePath(o, options.plone) for o in obj.getRelatedItems()])
        except AttributeError:
            related_items = ''
            related_items_paths = ''

        # write to INI file
        print >>fp, '[%s]' % _getUID(obj)
        print >>fp, 'path = %s' % _getRelativePath(obj, options.plone)
        print >>fp, 'id = %s' % obj.getId()
        print >>fp, 'portal_type = %s' % obj.portal_type
        print >>fp, 'uid = %s' % _getUID(obj)
        print >>fp, 'related_items = %s' % related_items
        print >>fp, 'related_items_paths = %s' % related_items_paths
        print >>fp, 'default_page = %s' % obj_data['metadata']['default_page']
        print >>fp, 'wf_policy = %s' % obj_data['metadata']['wf_policy']
        print >>fp, 'owner = %s' % obj_data['metadata']['owner']
        print >>fp, 'creators = %s' % ','.join(obj_data['schemadata'].get('creators', ''))
        print >>fp, 'position_parent = %d' % obj_data['metadata']['position_parent']
        print >>fp, 'local_roles_block = %d' % obj_data['metadata']['local_roles_block'] 
        print >>fp

        # dump data as pickle
        pickle_name = os.path.join(export_dir, _getUID(obj))
        try:
           cPickle.dump(obj_data, file(pickle_name, 'wb'))
        except:
            for x, item in obj_data['schemadata'].items():
                print x
                cPickle.dumps(item)

    fp.close()

    if errors:
        log('Errors')    
        for e in errors:
            log(e)

    log('Stats')
    log('%d items exported' % num_exported)


def export_site(app, options):

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

#    app = Zope.app()
    app = makerequest(app)
    uf = app.acl_users
    user = uf.getUser(options.username)
    if user is None:
        raise ValueError('Unknown user: %s' % options.username)
    newSecurityManager(None, user.__of__(uf))

    # inject some extra data instead creating our own datastructure
    options.export_directory = export_dir
    options.plone = makerequest(plone)
    # The export show starts here
    export_members(options)
    export_groups(options)
    export_placeful_workflow(options)
    export_structure(options)
    export_content(options)

    log('Export done...releasing memory und Tschuessn')


def main():
    from optparse import OptionParser
    from AccessControl.SecurityManagement import newSecurityManager
    import Zope
    gc.enable()
    app = Zope.app()
    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-p', '--path', dest='path', default='')
    parser.add_option('-o', '--output', dest='output', default='')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      default=False)

    options, args = parser.parse_args()
    options.app = app
    export_site(app, options)

if __name__ == '__main__':
    main()
