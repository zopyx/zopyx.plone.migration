################################################################
# Poor men's Plone import
# (C) 2013, ZOPYX Ltd, D-72074 Tuebingen
################################################################

import os
import shutil
import transaction
import urllib2
import cPickle
import sys
import lxml.html
from optparse import OptionParser
from datetime import datetime
from ConfigParser import ConfigParser

from DateTime.DateTime import DateTime
from Testing.makerequest import makerequest
from AccessControl.SecurityManagement import newSecurityManager
from App.config import getConfiguration
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.factory import addPloneSite
from Products.CMFPlone.utils import _createObjectByType
from Products.CMFPlacefulWorkflow.WorkflowPolicyConfig import \
    WorkflowPolicyConfig
from Products.CMFPlacefulWorkflow.PlacefulWorkflowTool import \
    WorkflowPolicyConfig_id

# check for LinguaPlone
try:
    import Products.LinguaPlone  # noqa
    HAS_LINGUAPLONE = True
except ImportError:
    HAS_LINGUAPLONE = False

parser = OptionParser()
parser.add_option(
    '-u',
    '--user',
    dest='username',
    default='admin'
)
parser.add_option(
    '-x',
    '--extension-profiles',
    dest='extension_profiles',
    default=''
)
parser.add_option(
    '-i',
    '--input',
    dest='input_directory',
    default=''
)
parser.add_option(
    '-d',
    '--dest-folder',
    dest='dest_folder',
    default=''
)
parser.add_option(
    '-s',
    '--site-id',
    dest='site_id',
    default=None
)
parser.add_option(
    '-t',
    '--timestamp',
    dest='timestamp',
    action='store_true'
)
parser.add_option(
    '-v',
    '--verbose',
    dest='verbose',
    action='store_true',
    default=False
)

IGNORED_FIELDS = ('id', 'relatedItems')
IGNORED_TYPES = (
    #    'Topic',
    #    'Ploneboard',
    #    'PloneboardForum',
    #    'NewsletterTheme',
    #    'Newsletter',
    #    'GMap',
    #    'Collage',
    #    'CollageRow',
    #    'CollageColumn',
    #    'FormFolder',
    #    'PloneboardConversation',
    #    'PloneboardComment',
    'Section',
    'NewsletterBTree',
    'NewsletterReference',
    'NewsletterRichReference',
    'CalendarXFolder',
)

FIXUIDTYPES = (
    'Document',
    'Page',
    'News Item',
    'ENLIssue',
    'WalserDocument',
    'WalserTimelineEvent'
)

PT_REPLACE_MAP = {
    'NewsletterTheme': 'EasyNewsletter',
    #    'NewsletterTheme' : 'ENLIssue',
    'Newsletter': 'ENLIssue',
    'GMap': 'GeoLocation',
    #    'Topic': 'Collection',
}
LAYOUT_REPLACE_MAP = {
    ('WalserDictionary', 'base_view'): 'walserdictionary_view',
    ('WalserTimeline', 'base_view'): 'walsertimeline_view',
}


def import_plonegazette_subscribers(options, newsletter, old_uid):
    """ Import PloneGazette subsribers into a new EasyNewsletter instance """

    log('Importing subscribers %s' % newsletter.absolute_url(1))
    subscribers_ini = os.path.join(
        options.input_directory,
        '%s_plonegazette_subscribers' % old_uid
    )
    CP = ConfigParser()
    CP.read([subscribers_ini])
    get = CP.get
    if newsletter.portal_type == 'EasyNewsletter':
        parent = newsletter
    else:
        parent = newsletter.aq_parent
    for section in CP.sections():
        id_ = get(section, 'id')
        if id_ not in parent.objectIds():
            parent.invokeFactory('ENLSubscriber', id=id_)
            subscriber = parent[id_]
            subscriber.setTitle(get(section, 'fullname'))
            subscriber.setFullname(get(section, 'fullname'))
            subscriber.setEmail(get(section, 'email'))


def import_placeful_workflow(options):
    import_dir = os.path.join(options.input_directory, 'placeful_workflow')
    if not os.path.exists(import_dir):
        return
    cfg = getConfiguration()
    try:
        pwt = options.plone.portal_placeful_workflow
    except AttributeError:
        return
    dest_dir = os.path.join(cfg.instancehome, 'import')
    if not os.path.exists(dest_dir):
        os.mkdir(dest_dir)
    for zexp in os.listdir(import_dir):
        zexp_id = zexp.replace('.zexp', '')
        src = os.path.join(import_dir, zexp)
        dest = os.path.join(dest_dir, zexp)
        shutil.copy(src, dest)
        log('Copied %s to %s' % (src, dest))
        if zexp_id in pwt.objectIds():
            pwt.manage_delObjects(zexp_id)
        pwt.manage_importObject(zexp)
        log('Imported %s' % zexp)


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
    pr.addMember('dummyadmin', 'dummyadmin', roles=('Member',))

    for section in CP.sections():
        username = get(section, 'username')
        if options.verbose:
            log('-> %s' % username)

        # omit group accounts
        if username.startswith('group_'):
            continue

        roles = get(section, 'roles').split(',') + ['Member']

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
                                        fullname=get(section, 'fullname'),))
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
    for section in CP.sections():
        grp_id = get(section, 'name')
        members = get(section, 'members').split(',')
        if options.verbose:
            log('-> %s' % grp_id)

        roles = get(section, 'roles').split(',')
        groups_tool.addGroup(grp_id, roles=roles)
        grp = groups_tool.getGroupById(grp_id)
        if grp is None:
            log('   Error while creating group %s' % grp_id)
            continue
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
        if c not in current.objectIds():
            _createObjectByType('Folder', current, id=c)
            # current.invokeFactory('Folder', id=c)
        current = getattr(current, c)
    if not components[-1] in current.objectIds():
        try:
            constrainsMode = current.getConstrainTypesMode()
        except AttributeError:
            constrainsMode = None
        if constrainsMode is not None:
            current.setConstrainTypesMode(0)

        # current.invokeFactory(PT_REPLACE_MAP.get(portal_type,
        #                       portal_type), id=components[-1])
        _createObjectByType(
            PT_REPLACE_MAP.get(portal_type, portal_type),
            current,
            id=components[-1]
        )
        if constrainsMode is not None:
            current.setConstrainTypesMode(constrainsMode)
    return current[components[-1]]


def myRestrictedTraverse(obj, path):
    """ traversal w/o acquisition """
    current = obj
    for p in path.split('/'):
        if p in current.objectIds():
            current = current[p]
        else:
            return None
    return current


def changeOwner(obj, owner):
    try:
        obj.plone_utils.changeOwnershipOf(obj, owner)
    except KeyError:
        obj.plone_utils.changeOwnershipOf(obj, 'dummyadmin')
    if owner != 'Anonymous User':
        obj.setCreators([owner])


def setLocalRoles(obj, local_roles):
    if not local_roles:
        return
    for userid, roles in local_roles:
        obj.manage_setLocalRoles(userid, roles)


def setLayout(obj, layout):
    if not layout:
        return
    layout = LAYOUT_REPLACE_MAP.get((obj.portal_type, layout), layout)
    layouts = []
    fti = obj.getTypeInfo()
    if fti:
        layouts = fti.getAvailableViewMethods(obj)
    if layout in layouts:
        obj.setLayout(layout)
    else:
        log('Can not set layout %s on %s (%s)' % (
            layout, obj.absolute_url(), fti.getId()))


def setWFPolicy(obj, wf_policy):
    if not wf_policy:
        return
    i = WorkflowPolicyConfig(
        wf_policy['workflow_policy_in'],
        wf_policy['workflow_policy_below']
    )
    setattr(obj, WorkflowPolicyConfig_id, i)


def setExcludeFromNav(obj, options):
    """ Force exclude from navigation for certain portal_types
        in the Plone root only.
    """
    if obj.aq_parent.getId() == options.plone.getId() and \
       obj.portal_type in ('File', 'Image', 'Page', 'Document', 'News Item'):
        obj.setExcludeFromNav(True)


def setObjectPosition(obj, position):
    if HAS_LINGUAPLONE:
        return
    try:
        obj.aq_parent.moveObjectToPosition(obj.getId(), position)
    except:
        return
    newpos = obj.aq_parent.getObjectPosition(obj.getId())
    if newpos != position:
        log('Position was not set correctly for %s.' % obj.getId())


def setContentType(obj, content_type):
    obj.setContentType(content_type)
    obj.content_type = content_type
    if obj.portal_type == 'File':
        obj.__annotations__[
            'Archetypes.storage.AnnotationStorage-file'
        ].setContentType(content_type)
        obj.__annotations__[
            'Archetypes.storage.AnnotationStorage-file'
        ].setFilename(obj.getId())


def setLocalRolesBlock(obj, value):
    obj.__ac_local_roles_block__ = value
    obj.reindexObjectSecurity()


def fix_resolve_uids(obj, options):

    def xpath_query(node_names):
        if not isinstance(node_names, (list, tuple)):
            raise TypeError('"node_names" must be a list or tuple (not %s)'
                            % type(node_names))
        return './/*[%s]' % \
            ' or '.join(['name()="%s"' % name for name in node_names])

    html = obj.getRawText()
    if not html:
        return
    if not isinstance(html, unicode):
        html = unicode(html, 'utf-8')
    try:
        root = lxml.html.fromstring(html)
    except:
        log("Cant parse html with lxml at %s" % obj.getId())
        return
    for node in root.xpath(xpath_query(('img', 'a'))):
        url = ''
        if node.tag == 'img':
            url = node.attrib.get('src', '')
        elif node.tag == 'a':
            url = node.attrib.get('href', '')

        if not url.startswith('resolveuid'):
            continue
        url_f = url.split('/')
        old_uid = url_f[1]
        pickle_filename = os.path.join(options.input_directory,
                                       'content', old_uid)
        if not os.path.exists(pickle_filename):
            log('resolve uid failed, old uid does not exist: %s' %
                pickle_filename)
            continue

        old_data = cPickle.load(open(pickle_filename))
        old_path = old_data['metadata']['path']
        new_obj = myRestrictedTraverse(options.plone, old_path)
        if new_obj is None:
            continue
        url_f[1] = new_obj.UID()
        url = '/'.join(url_f)
        if node.tag == 'img':
            node.attrib['src'] = url
        elif node.tag == 'a':
            node.attrib['href'] = url

    html = lxml.html.tostring(root, encoding=unicode)
    obj.setText(html)


def reindexObject(obj, modified=None):
    """ restores original modified date (if given) and reindexes object """
    if modified:
        obj.setModificationDate(modified)
    obj.reindexObject(idxs=['suppress_notifyModified', ])


##############################################################################
# Taken from http://glenfant.wordpress.com/2010/04/02/changing-workflow-state-
# quickly-on-cmfplone-content/
# and slightly adjusted
##############################################################################


def setReviewState(content, state_id, acquire_permissions=False,
                   portal_workflow=None, **kw):
    """Change the workflow state of an object
    @param content: Content obj which state will be changed
    @param state_id: name of the state to put on content
    @param acquire_permissions: True->All permissions unchecked and on riles
                                and acquired
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
    wf_id = wf_def.getId()

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
        if k not in wf_state:
            del kw[k]
    if 'review_state' in kw:
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
    content.reindexObject(idxs=['allowedRolesAndUsers', 'review_state',
                                'suppress_notifyModified'])
    return


def update_content(options, new_obj, old_uid):
    """ Update schema data of 'new_obj' with the pickled
        data for 'old_uid'.
    """

    pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
    if not os.path.exists(pickle_filename):
        return
    obj_data = cPickle.load(file(pickle_filename))

    for k, v in obj_data['schemadata'].items():
        if k in IGNORED_FIELDS:
            continue
        field = new_obj.Schema().getField(k)
        if field:
            if field.type == "reference":
                # reference fields are handled later
                continue
            if isinstance(v, basestring) and v.startswith('file://'):
                v = urllib2.urlopen(v).read()
            try:
                field.set(new_obj, v)
            except Exception, e:
                log('Could not update field %s of %s (error=%s)' %
                    (field.getName(), new_obj.absolute_url(), e))

    setLocalRolesBlock(new_obj, obj_data['metadata']['local_roles_block'])
    setObjectPosition(new_obj, obj_data['metadata']['position_parent'])
    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
    setLayout(new_obj, obj_data['metadata']['layout'])
    setWFPolicy(new_obj, obj_data['metadata']['wf_policy'])
    setExcludeFromNav(new_obj, options)
    setContentType(new_obj, obj_data['metadata']['content_type'])
    reindexObject(new_obj, obj_data['schemadata']['modification_date'])


def create_new_obj(options, folder, old_uid):
    if not old_uid:
        return

    pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
    if not os.path.exists(pickle_filename):
        return
    obj_data = cPickle.load(file(pickle_filename))
    id_ = obj_data['metadata']['id']
    path_ = obj_data['metadata']['path']
    portal_type_ = obj_data['metadata']['portal_type']
    candidate = myRestrictedTraverse(options.plone, path_)
    if candidate is None or candidate.portal_type != portal_type_:
        if obj_data['metadata']['portal_type'] in IGNORED_TYPES:
            return
        try:
            constrainsMode = folder.getConstrainTypesMode()
        except AttributeError:
            constrainsMode = None
        if constrainsMode is not None:
            folder.setConstrainTypesMode(0)
        pt = obj_data['metadata']['portal_type']
        if id_ not in folder.objectIds():
            _createObjectByType(
                PT_REPLACE_MAP.get(pt, pt),
                folder,
                id_
            )
            if constrainsMode is not None:
                folder.setConstrainTypesMode(constrainsMode)
        new_obj = folder[id_]
    else:
        new_obj = candidate

    for k, v in obj_data['schemadata'].items():
        if k in IGNORED_FIELDS:
            continue
        field = new_obj.Schema().getField(k)
        if field is None or field.type == "reference":
            continue
        if isinstance(v, basestring) and v.startswith('file://'):
            v = urllib2.urlopen(v).read()
        try:
            field.set(new_obj, v)
        except Exception, e:
            log('Unable to set %s for %s (%s)' %
                (k, new_obj.absolute_url(1), e))

    setLocalRolesBlock(new_obj, obj_data['metadata']['local_roles_block'])
    setObjectPosition(new_obj, obj_data['metadata']['position_parent'])
    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
    setLayout(new_obj, obj_data['metadata']['layout'])
    setWFPolicy(new_obj, obj_data['metadata']['wf_policy'])
    setExcludeFromNav(new_obj, options)
    setContentType(new_obj, obj_data['metadata']['content_type'])
    reindexObject(new_obj, obj_data['schemadata']['modification_date'])


def import_topic_criterions(options, topic, criterion_ids, old_uid):
    pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
    if not os.path.exists(pickle_filename):
        return
    obj_data = cPickle.load(file(pickle_filename))
    for crit_id in criterion_ids:
        crit_data = obj_data['topic_criterions'].get(crit_id)
        if not crit_data \
           or not crit_data.get('portal_type') \
           or not crit_data.get('field'):
            # disabled suptopic support
            continue
        if crit_data['portal_type'] == "ATDateCriteria":
            crit_data['portal_type'] = 'ATFriendlyDateCriteria'
        crit = topic.addCriterion(crit_data['field'], crit_data['portal_type'])
        if not crit:
            continue
        crit_schema = crit.aq_base.Schema()
        for field in crit_schema.fields():
            name = field.getName()
            if name in IGNORED_FIELDS:
                continue
            value = crit_data.get(name)
            if field.type == "reference":
                value = uids_to_references(options, topic, value)
            if value:
                field.set(crit, value)


def uids_to_references(options, context, old_uids):
    if isinstance(old_uids, basestring):
        old_uids = (old_uids, )
    new_refs = []
    for uid in old_uids:
        pickle_filename = os.path.join(options.input_directory, 'content', uid)
        if os.path.exists(pickle_filename):
            old_data = cPickle.load(open(pickle_filename))
            old_path = old_data['metadata']['path']
            new_obj = context.restrictedTraverse(old_path, None)
            if new_obj is not None:
                new_refs.append(new_obj)
            else:
                log("Could not find path for old object (%s)" % old_data)
    return new_refs


def import_content(options):

    installed_products = [
        p['id'] for p in
        options.plone.portal_quickinstaller.listInstalledProducts()
    ]

    log('Importing Content')
    structure_ini = os.path.join(options.input_directory, 'structure.ini')
    CP = ConfigParser()
    CP.read([structure_ini])
    sections = CP.sections()
    sections.sort(lambda x, y: cmp(int(x), int(y)))

    # Recreate folderish structure first
    log('Creating hierarchy structure first')
    num_sections = len(sections)
    for i, section in enumerate(sections):
        if i == 0:  # Plone site
            continue
        if options.verbose:
            log('--> (%d/%d) %s' %
                ((i + 1), num_sections, CP.get(section, 'path')))
        uid = CP.get(section, 'uid')
        path = CP.get(section, 'path')
        portal_type = CP.get(section, 'portal_type')
        if portal_type in IGNORED_TYPES:
            continue
        try:
            new_obj = folder_create(options.plone, path, portal_type)
        except Exception, msg:
            log('Could not create %s: %s' % (path, msg))
            continue
        if uid:
            update_content(options, new_obj, uid)
        if portal_type in ('Newsletter', 'NewsletterTheme'):
            import_plonegazette_subscribers(options, new_obj, uid)

    transaction.savepoint()

    # Now recreate the child objects within
    log('Creating content')
    for i, section in enumerate(sections):
        if options.verbose:
            log('--> (%d/%d) %s' %
                ((i + 1), num_sections, CP.get(section, 'path')))
        uids = CP.get(section, 'children_uids').split(',')
        if i == 0:
            current = options.plone
        else:
            path = CP.get(section, 'path')
            if CP.get(section, 'portal_type') in IGNORED_TYPES:
                continue
            current = options.plone.restrictedTraverse(path)
        for uid in uids:
            try:
                create_new_obj(options, current, uid)
            except ValueError, msg:
                log('Could not create new object: %s' % msg)

        log('--> %d children created' % len(uids))

        if i % 10 == 0:
            transaction.savepoint()

    # set default pages
    log('Setting default pages')
    for i, section in enumerate(sections):
        # Default page
        try:
            default_page = CP.get(section, 'default_page')
        except:
            default_page = None
        if default_page:
            path = CP.get(section, 'path')
            obj = myRestrictedTraverse(options.plone, path)
            try:
                child_ids = obj.objectIds()
            except AttributeError:
                child_ids = []
            if default_page in child_ids:
                log('Setting default page for %s to %s' %
                    (obj.absolute_url(1), default_page))
                obj.setDefaultPage(default_page)
                obj.default_page = default_page

    # Now using content.ini for post migration fix-up
    content_ini = os.path.join(options.input_directory, 'content.ini')
    CP = ConfigParser()
    CP.read([content_ini])
    sections = CP.sections()
    log('Post migration fix-up (content.ini)')
    for i, section in enumerate(sections):

        # Topic
        if CP.get(section, 'portal_type') == 'Topic':
            id_ = CP.get(section, 'id')
            path = CP.get(section, 'path')
            old_uid = CP.get(section, 'uid')
            crit_ids = CP.get(section, 'topic_criterions').split(',')
            obj = myRestrictedTraverse(options.plone, path)
            if obj:
                import_topic_criterions(options, obj, crit_ids, old_uid)
                log("Fixed topic criterions for %s" % path)

        # Flowplayer
        if CP.get(section, 'portal_type') == 'File':
            id_ = CP.get(section, 'id')
            path = CP.get(section, 'path')
            obj = myRestrictedTraverse(options.plone, path)
            basename, ext = os.path.splitext(id_)
            if ext.lower() in ('.mp3', '.mp4', '.wmv') \
               and 'collective.flowplayer' in installed_products:
                log('Setting flowplayer view on %s' % obj.absolute_url(1))
                obj.selectViewTemplate('flowplayer')

        # reference fields
        path = CP.get(section, 'path')
        obj_pickle_filename = os.path.join(
            options.input_directory,
            'content', CP.get(section, 'uid'))
        obj_data = cPickle.load(open(obj_pickle_filename))
        obj = myRestrictedTraverse(options.plone, path)
        if obj is not None:
            for f in obj.Schema().filterFields(type='reference'):
                name = f.getName()
                old_uids = obj_data['schemadata'].get(name, [])
                new_refs = uids_to_references(options, obj, old_uids)
                if len(new_refs) > 0:
                    if options.verbose:
                        log("--> New References for %s (%s): %s" %
                            (name, path, new_refs))
                    f.set(obj, new_refs)
        if HAS_LINGUAPLONE and 'translations' in obj_data \
           and len(obj_data['translations']):
            obj.setCanonical()
            for lang, translation_path in obj_data['translations'].items():
                translation = myRestrictedTraverse(
                    options.plone,
                    translation_path
                )
                translation.addTranslationReference(obj)
                if options.verbose:
                    log("--> Connected Translation from [%s] %s to [%s] %s "
                        % (path, obj.getLanguage(),
                           translation_path, translation.Language(), ))


def log(s):
    print >> sys.stdout, s


def fixup_uids(options):
    query = {'portal_type': FIXUIDTYPES}
    if HAS_LINGUAPLONE:
        query['Language'] = 'all'
    for brain in options.plone.portal_catalog(**query):
        fix_resolve_uids(brain.getObject(), options)


def setup_plone(app, dest_folder, site_id, products=(), profiles=()):
    app = makerequest(app)
    dest = app
    if dest_folder:
        if dest_folder not in app.objectIds():
            log("Creating destination Folder: '%s'" % dest_folder)
            app.manage_addFolder(id=dest_folder)
        dest = dest.restrictedTraverse(dest_folder)
    if site_id in dest.objectIds():
        log('%s already exists in %s - REMOVING IT' %
            (site_id, dest.absolute_url(1)))
        if dest.meta_type != 'Folder':
            raise RuntimeError(
                'Destination must be a Folder instance (found %s)' %
                dest.meta_type)
        dest.manage_delObjects([site_id])
        transaction.commit()
    log('Creating new Plone site with extension profiles %s' % profiles)
    addPloneSite(
        dest,
        site_id,
        create_userfolder=True,
        extension_ids=profiles,
        setup_content=False
    )
    plone = dest[site_id]
    log('Created Plone site at %s' % plone.absolute_url(1))
    qit = plone.portal_quickinstaller

    ids = [p['id'] for p in qit.listInstallableProducts(skipInstalled=1)]
    for product in products:
        if product in ids:
            qit.installProduct(product)
    if 'front-page' in plone.objectIds():
        plone.manage_delObjects('front-page')
    return plone


def import_plone(options):

    if not os.path.exists(options.input_directory):
        raise ValueError('Input directory does not exist')

    log('#' * 80)
    log(options.input_directory)
    log('#' * 80)

    if options.site_id is None:
        site_id = options.input_directory.rstrip('/').rsplit('/', 1)[-1]
    else:
        site_id = options.site_id

    profiles = []

    if options.extension_profiles:
        ext_profiles = options.extension_profiles.split(',')
        profiles.extend(ext_profiles)
    if not profiles:
        profiles = ['plonetheme.sunburst:default']
    if options.timestamp:
        site_id += '_' + datetime.now().strftime('%Y%m%d-%H%M%S')

    # options.plone = myRestrictedTraverse(options.app, site_id)
    options.plone = setup_plone(
        options.app,
        options.dest_folder,
        site_id,
        profiles=profiles
    )
    import_members(options)
    import_groups(options)
    import_placeful_workflow(options)
    import_content(options)
    fixup_uids(options)
    return options.plone.absolute_url(1)


def import_site(options):

    uf = options.app.acl_users
    user = uf.getUser(options.username)
    if user is None:
        raise ValueError('Unknown user: %s' % options.username)
    newSecurityManager(None, user.__of__(uf))

    url = import_plone(options)
    log('Committing...')
    transaction.commit()
    log('done')
    log(url)


def main():
    import Zope2
    app = Zope2.app()
    sys.argv = [__file__] + sys.argv[3:]
    options, args = parser.parse_args()
    options.app = app
    import_site(options)

if __name__ == '__main__':
    main()
