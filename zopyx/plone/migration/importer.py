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
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.factory import addPloneSite
from Products.CMFPlone.utils import _createObjectByType

IGNORED_FIELDS = ('id', 'relatedItems')
IGNORED_TYPES = ('Topic', 
'Ploneboard', 
'PloneboardForum', 
'NewsletterTheme', 
'Newsletter', 
'Section', 
'NewsletterBTree', 
'CalendarXFolder',
'GMap',
'Collage', 
'CollageRow', 
'CollageColumn',
'FormFolder',
'PloneboardConversation',
'PloneboardComment',
)

def import_members(options):
    log('Importing members')
    pr = options.plone.portal_registration
    pm = options.plone.portal_membership
    members_ini = os.path.join(options.input_directory, 'members.ini')

    CP = ConfigParser()
    CP.read([members_ini])
    get = CP.get

    count = 0
    errors = list()
    for section in CP.sections():
        username = get(section, 'username')
        if options.verbose:
            log('-> %s' % username)

        # omit group accounts
        if username.startswith('group_'):
            continue
        
        roles = get(section, 'roles').split('/') + ['Member']
    
        try:
            pr.addMember(username, 
                         get(section, 'password'), 
                         roles=roles)
        except Exception, e:
            errors.append(dict(username=username, error=e))
            continue
        count += 1
        member = pm.getMemberById(username)
        pm.createMemberArea(username)
        member.setMemberProperties(dict(email=get(section, 'email'),
                                        fullname=get(section, 'fullname'),
                                  ))
    if errors:
        log('Errors')
        for e in errors:
            log(e)
    log('%d members imported' % count)

def import_groups(options):
    log('Importing groups')
    groups_tool = options.plone.portal_groups
    groups_ini = os.path.join(options.input_directory, 'groups.ini')

    CP = ConfigParser()
    CP.read([groups_ini])
    get = CP.get

    count = 0
    errors = list()
    for section in CP.sections():
        grp_id = get(section, 'name')
        members = get(section, 'members').split(',')
        if options.verbose:
            log('-> %s' % grp_id)

        roles = get(section, 'roles').split('/')
        groups_tool.addGroup(grp_id)    
        grp = groups_tool.getGroupById(grp_id)
        for member in members:
            grp.addMember(member)
        count += 1
                                  
    log('%d groups imported' % count)


def folder_create(root, dirname, portal_type):

    current = root
    components = dirname.split('/')
    for c in components[:-1]:
        if not c: 
            continue
        if not c in current.objectIds():
            #_createObjectByType('Folder', current, id=c)
            current.invokeFactory('Folder', id=c)
        current = getattr(current, c)
    if not components[-1] in current.objectIds():
        try:
            constrainsMode = current.getConstrainTypesMode()
        except AttributeError:
            constrainsMode = None
        if constrainsMode is not None:
            current.setConstrainTypesMode(0)
        current.invokeFactory(portal_type, id=components[-1])
        if constrainsMode is not None:
            current.setConstrainTypesMode(constrainsMode)
    return current[components[-1]]

def changeOwner(obj, owner):
    try:
        obj.plone_utils.changeOwnershipOf(obj, owner)
    except KeyError:
        obj.plone_utils.changeOwnershipOf(obj, 'admin')
    obj.setCreators([owner])

def setLocalRoles(obj, local_roles):
    if not local_roles:
        return
    for userid, roles in local_roles:
        obj.manage_setLocalRoles(userid, roles)

def setExcludeFromNav(obj):
    if obj.portal_type in ('File', 'Image', 'Page', 'Document', 'News Item'):
        obj.setExcludeFromNav(True)

#############################################################################################################
# Taken from http://glenfant.wordpress.com/2010/04/02/changing-workflow-state-quickly-on-cmfplone-content/
# and slightly adjusted
#############################################################################################################

def setReviewState(content, state_id, acquire_permissions=False,
                        portal_workflow=None, **kw):
    """Change the workflow state of an object
    @param content: Content obj which state will be changed
    @param state_id: name of the state to put on content
    @param acquire_permissions: True->All permissions unchecked and on riles and
                                acquired
                                False->Applies new state security map
    @param portal_workflow: Provide workflow tool (optimisation) if known
    @param kw: change the values of same name of the state mapping
    @return: None
    """
    if portal_workflow is None:
        portal_workflow = getToolByName(content, 'portal_workflow')

    # Might raise IndexError if no workflow is associated to this type

    workflows = portal_workflow.getWorkflowsFor(content)
    if not workflows:
        return 
    wf_def = workflows[0]
    wf_id= wf_def.getId()

    wf_state = {
        'action': None,
        'actor': None,
        'comments': "Setting state to %s" % state_id,
        'review_state': state_id,
        'time': DateTime(),
        }

    # Updating wf_state from keyword args
    for k in kw.keys():
        # Remove unknown items
        if not wf_state.has_key(k):
            del kw[k]
    if kw.has_key('review_state'):
        del kw['review_state']
    wf_state.update(kw)

    portal_workflow.setStatusOf(wf_id, content, wf_state)

    if acquire_permissions:
        # Acquire all permissions
        for permission in content.possible_permissions():
            content.manage_permission(permission, acquire=1)
    else:
        # Setting new state permissions
        wf_def.updateRoleMappingsFor(content)

    # Map changes to the catalogs
    content.reindexObject(idxs=['allowedRolesAndUsers', 'review_state'])
    return


def update_content(options, new_obj, old_uid):
    """ Update schema data of 'new_obj' with the pickled
        data for 'old_uid'.
    """

    pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
    if not os.path.exists(pickle_filename):
        return
    obj_data = cPickle.load(file(pickle_filename))

    for k,v in obj_data['schemadata'].items():
        if k in IGNORED_FIELDS:
            continue
        field = new_obj.Schema().getField(k)
        if field:
            field.set(new_obj, v)
    
    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
    setExcludeFromNav(new_obj)
    new_obj.reindexObject()

def create_new_obj(plone, folder, old_uid):
    if not old_uid:
        return
    pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
    if not os.path.exists(pickle_filename):
        return
    obj_data = cPickle.load(file(pickle_filename))
    id_ = obj_data['schemadata']['id']
    path_ = obj_data['metadata']['path']
    candidate = plone.restrictedTraverse(path_, None)
    if candidate is None:
        if obj_data['metadata']['portal_type'] in IGNORED_TYPES:
            return
        try:
            constrainsMode = folder.getConstrainTypesMode()
        except AttributeError:
            constrainsMode = None
        if constrainsMode is not None:
            folder.setConstrainTypesMode(0)
        folder.invokeFactory(obj_data['metadata']['portal_type'], id=id_)
        if constrainsMode is not None:
            folder.setConstrainTypesMode(constrainsMode)
        new_obj = folder[id_]
    else:
        new_obj = candidate
    for k,v in obj_data['schemadata'].items():
        if k in IGNORED_FIELDS:
            continue
        field = new_obj.Schema().getField(k)
        if field is None:
            continue
        if isinstance(v, basestring) and v.startswith('file://'):
            v = urllib2.urlopen(v).read()
        try:
            field.set(new_obj, v)
        except Exception, e:
            log('Unable to set %s for %s (%s)' % (k, new_obj.absolute_url(1), e))
            

    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
    setExcludeFromNav(new_obj)
    new_obj.reindexObject()


def import_content(options):
    log('Importing Content')
    structure_ini = os.path.join(options.input_directory, 'structure.ini')
    CP = ConfigParser()
    CP.read([structure_ini])
    get = CP.get

    sections = CP.sections()
    sections.sort(lambda x,y: cmp(int(x), int(y)))

    # Recreate folderish structure first
    log('Creating hierarchy structure first')
    num_sections = len(sections)
    for i, section in enumerate(sections):
        if i==0: # Plone site
            continue
        if options.verbose:
            log('--> (%d/%d) %s' % (i, num_sections, CP.get(section, 'path')))
        id = CP.get(section, 'id')
        uid = CP.get(section, 'uid')
        path = CP.get(section, 'path')
        portal_type = CP.get(section, 'portal_type')
        if portal_type in IGNORED_TYPES:
            continue
        new_obj = folder_create(options.plone, path, portal_type)
        if uid:
            update_content(options, new_obj, uid)

    transaction.savepoint()

    # Now recreate the child objects within
    log('Creating content')
    for i, section in enumerate(sections):
        if options.verbose:
            log('--> (%d/%d) %s' % (i, num_sections, CP.get(section, 'path')))
        uids = CP.get(section, 'children_uids').split(',')
        if i == 0:
            current = options.plone
        else:
            path = CP.get(section, 'path')
            if CP.get(section, 'portal_type') in IGNORED_TYPES:
                continue
            current = options.plone.restrictedTraverse(path)
        for uid in uids:
            create_new_obj(options.plone, current, uid)
        log('--> %d children created' % len(uids))

        if i % 10 == 0:
            transaction.savepoint()


    # Now using content.ini for post migration fix-up
    content_ini = os.path.join(options.input_directory, 'content.ini')
    CP = ConfigParser()
    CP.read([content_ini])
    get = CP.get

    sections = CP.sections()
    log('Post migration fix-up')
    for i, section in enumerate(sections):
        related_items_paths = CP.get(section, 'related_items_paths').split(',')
        if related_items_paths:
            path = CP.get(section, 'path')
            obj = options.plone.restrictedTraverse(path,None)
            if obj is not None:
                ref_objs = []
                for related_items_path in related_items_paths:
                    o = options.plone.restrictedTraverse(related_items_path, None)
                    if o is not None:
                        ref_objs.append(o)
                obj.setRelatedItems(ref_objs)                                            


def log(s):
    print >>sys.stdout, s

def setup_plone(app, dest_folder, site_id, products=(), profiles=()):
    dest = makerequest(app)
    if dest_folder:
        if not dest_folder in app.objectIds():
            manage_addFolder(app, dest_folder)
        dest = app[dest_folder]
    addPloneSite(dest, site_id, create_userfolder=True, extension_ids=profiles)
    plone = dest[site_id]
    log('Created Plone site at %s' % plone.absolute_url(1))
    qit = plone.portal_quickinstaller

    ids = [p['id'] for p in qit.listInstallableProducts(skipInstalled=1) ]
    for product in products:
        if product in ids:
            qit.installProduct(product)
    if 'front-page' in plone.objectIds():
        plone.manage_delObjects('front-page')
    return plone

def import_plone(app, options):

    if not os.path.exists(options.input_directory):
        raise ValueError('Input directory does not exist')

    log('#'*80)
    log(options.input_directory)
    log('#'*80)

    site_id = options.input_directory.rstrip('/').rsplit('/', 1)[-1]
    profiles = ['plonetheme.sunburst:default']
    ext_profiles = options.extension_profiles.split(',')
    profiles.extend(ext_profiles)
    if options.timestamp:
        site_id += '_' + datetime.now().strftime('%Y%m%d-%H%M%S')

    plone = setup_plone(app, options.dest_folder, site_id, profiles=profiles)
    options.plone = plone
    import_members(options)
    import_groups(options)
    import_content(options)
    return plone.absolute_url(1)

def import_site(options):

    uf = app.acl_users
    user = uf.getUser(options.username)
    if user is None:
        raise ValueError('Unknown user: %s' % options.username)
    newSecurityManager(None, user.__of__(uf))

    url = import_plone(app, options)
    log('Committing...')
    transaction.commit()
    log('done')
    log(url)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-x', '--extension-profiles', dest='extension_profiles', default='')
    parser.add_option('-i', '--input', dest='input_directory', default='')
    parser.add_option('-d', '--dest-folder', dest='dest_folder', default='sites')
    parser.add_option('-t', '--timestamp', dest='timestamp', action='store_true')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False)
    options, args = parser.parse_args()
    import_site(options)


