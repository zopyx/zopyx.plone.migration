################################################################
# Poor men's Plone export
# (C) 2013, ZOPYX Ltd, D-72074 Tuebingen
################################################################

import pytz
import time
import json
import os
import plone.api
import shutil
import tempfile
import glob
import transaction
import urllib2
import cPickle
import shutil
import lxml.html
import magic
import ldap
from zope.component import getUtility
from optparse import OptionParser
from datetime import datetime
from ConfigParser import ConfigParser

from DateTime.DateTime import DateTime
from OFS.Folder import manage_addFolder
from Testing.makerequest import makerequest
from AccessControl.SecurityManagement import newSecurityManager
from App.config import getConfiguration
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.factory import addPloneSite
from Products.CMFPlone.utils import _createObjectByType
from Products.CMFPlacefulWorkflow.WorkflowPolicyConfig import WorkflowPolicyConfig
from Products.CMFPlacefulWorkflow.PlacefulWorkflowTool import WorkflowPolicyConfig_id
from plone.namedfile.field import NamedBlobFile, NamedBlobImage
from plone import namedfile
from plone.app.textfield.value import RichTextValue
from plone.app.event.dx.behaviors import data_postprocessing
from zope.intid.interfaces import IIntIds

import sys

vcard_props = {
    'academic': 'academic',
    'bemerkung': 'description',
    'bundesland': 'state',
#    'db_projekte': 'db_projects',
#    'expertise': 'expertise',
#    'fachgebiete': 'specialties',
    'fon1': 'phone',
#    'geburtstag': 'birthday',
    'geschlecht': 'gender',
#    'institution': 'institution',
#    'institutsLocation': 'institution_location',
#    'kooperationsInteresse': 'cooperation_interests',
#    'mitgliedschaften': 'memberships',
    'plz': 'zip',
    'position': 'position',
#    'projekte': 'projects',
    'title': 'title',
}

IGNORED_FIELDS = ('id', 'relatedItems')


MAP_UNIVERSITY_STATUS = {
    'Uni': 'university',
    'Fachhochschule': 'college',
    'Kunst- und Musikhochschule': 'academy_of_arts',
    'Hochschulverbund': 'university_partnership',
    'Forschungseinrichtung': 'research_institute',
    'Vorgeschlagene Forschungseinrichtung': 'suggested_research_institute',
    'Sonstiges (Kein besonderer Ort)': 'other',
}

MAP_FACULTY = {
    'Agrar- und Forstwissenschaft'        :    'agrarian_economy',  
    'Geistes- und Sozialwissenschaften'   :    'humanities',        
    'Geowissenschaft'                     :    'geosciences',       
    'Informatik'                          :    'informatics',       
    'Ingenieurswissenschaften'            :    'engineering',       
    'Kunst, Design und Medienwissenschaft':    'media_studies',     
    'Medizin und Gesundheitswesen'        :    'medical_science',   
    'Naturwissenschaft und Mathematik'    :    'natural_science',   
    'Rechtswissenschaft'                  :    'law',               
    'Sportwissenschaft'                   :    'sport_science',     
    'Sprachen und Sprachwissenschaft'     :    'linguistics',       
    'Wirtschaftswissenschaften'           :    'economic_sciences', 
    'Sonstiges'                           :    'other'              
}

MAP_CATEGORY = {
    'Lernumgebung':                 'learning_environment',
    'Lernmaterial':      'learning_material',
    'Lernmaterial(-sammlung)':      'learning_material',
    'Software':                     'software',
    'Lehr-/Lernszenario':           'learning_scenario'
}


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

    def addMember(username, password, roles):
        try:
            pr.addMember(username, password, roles=roles)
        except ValueError as e:
            print 'User exists: {}, {}'.format(username, e)

    log('Importing members')
    pr = options.plone.portal_registration
    pm = options.plone.portal_membership
    md = options.plone.portal_memberdata
    ms = options.plone.portal_membership
    members_ini = os.path.join(options.input_directory, 'members.ini')

    CP = ConfigParser()
    CP.read([members_ini])
    get = CP.get

    count = 0
    errors = list()

    plone.api.group.create(groupname='CommunityMember',
                           title='Community Members',
                           roles=['Member'])

    plone.api.group.create(groupname='BaWueTeacher',
                           title='BaWue Teachers',
                           roles=['Member'])


    plone.api.group.create(groupname='UniversityEditor',
                           title='University Editors',
                           roles=['Member'])

    addMember('dummyadmin', 'dummyadmin', roles=('Member',))

    for section in CP.sections()[:]:

        username = get(section, 'username')
        print username

        if options.plone.acl_users.getUser(username):
            continue

#        if username != 'mschmidt1':
#            continue

        if len(username) == 1:
            username +='-2'
        elif len(username) == 2:
            username +='-2'
       
        email = get(section, 'email')
        if not email:
            continue

        if options.verbose:
            log('-> %s' % username)

        # omit group accounts
        if username.startswith('group_'):
            continue

        created = False
        for i in range(1, 4):
            try:
                time.sleep(0.1)
                plone.api.user.create(email=get(section, 'email'),
                                      username=username,
                                      password=get(section, 'password'),
                                      roles=('Member',))

                created = True
            except (AttributeError, ValueError) as e:
                log('-> Error: %s' % e)
                continue

        if not created:
            print 'Unable to create account {}'.format(username)
            continue

        roles = get(section, 'roles').split(',') 
        for role in roles:
            role = role.strip()
            if not role or role in ('Manager', 'Member'):
                continue
            plone.api.group.add_user(groupname=role, username=username)

        count += 1
        member = pm.getMemberById(username)
#        pm.createMemberArea(username)
        vcard = json.loads(get(section, 'vcard'))
        member_props = dict(email=get(section, 'email'),
                            fullname=get(section, 'fullname'))

        for k,v in vcard_props.items():
            value = vcard.get(k)
            if not value:
                continue
            
            if v in ['db_projects', 'specialties', 'cooperation_interests', 'memberships', 'projects']:
                if isinstance(value, list):
                    member_props[v] = value
                elif isinstance(value, basestring):
                    member_props[v] = [value]

            else:
                if isinstance(value, basestring):
                    member_props[v] = value


        import pprint
        pprint.pprint(member_props)
        if member is not None:
            try:
                member.setMemberProperties(member_props)
            except ldap.DECODING_ERROR:
                pass

        try:
            portrait_filename = get(section, 'portrait_filename')
        except:
            portrait_filename = None

        if portrait_filename:
            from OFS.Image import Image
            from Products.PlonePAS.utils import scale_image

            try:
                scaled, mimetype = scale_image(open(portrait_filename, 'rb'))
            except:
                continue

            portrait = Image(id=username, file=scaled, title='')
            membertool = getToolByName(options.plone, 'portal_memberdata')
            membertool._setPortrait(portrait, username)

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

        roles = get(section, 'roles').split(',')
        groups_tool.addGroup(grp_id)    
        groups_tool.editGroup(grp_id, roles=roles)
        grp = groups_tool.getGroupById(grp_id)
        for member in members:
            grp.addMember(member)
        count += 1
                                  
    log('%d groups imported' % count)

def target_pt(default_portal_type, id_, dirname):

    if default_portal_type in ('Event',):
        return default_portal_type

    if default_portal_type=='Medienbeitrag':
        return 'eteaching.policy.podcastitem'

    if default_portal_type == 'ETGeoLocation':
        return 'eteaching.policy.geolocation'

    if default_portal_type == 'Projektdarstellung':
        return 'eteaching.policy.project'

    if default_portal_type == 'PeleBlog':
        return 'eteaching.policy.blogentry'

    if default_portal_type == 'PraxisBericht':
        return 'eteaching.policy.experiencereport'

    if id_.startswith('vodcast') or id_.startswith('podcast'):
        return 'eteaching.policy.podcastchannel'

    return default_portal_type

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

        target_portal_type = target_pt('Folder', components[-1], dirname)
        current.invokeFactory(target_portal_type, id=components[-1])
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
    layout_ids = [id for id, title in obj.getAvailableLayouts()]
    if layout in layout_ids:
        obj.setLayout(layout)
    else:
        log('Can not set layout %s on %s' % (layout, obj.absolute_url()))

def setWFPolicy(obj, wf_policy):
    if not wf_policy:
        return
    i = WorkflowPolicyConfig(wf_policy['workflow_policy_in'], wf_policy['workflow_policy_below'])
    setattr(obj, WorkflowPolicyConfig_id, i)


def setExcludeFromNav(obj, options):
    """ Force exclude from navigation for certain portal_types
        in the Plone root only.
    """
    if obj.portal_type in ('File', 'Image'):
        obj.exclude_from_nav = True

def setObjectPosition(obj, position):
    try:
        obj.aq_parent.moveObjectToPosition(obj.getId(), position)
    except:
        return

def setContentType(obj, content_type):
    return
    obj.setContentType(content_type)
    obj.content_type = content_type
    if obj.portal_type == 'File':
        obj.__annotations__['Archetypes.storage.AnnotationStorage-file'].setContentType(content_type)
        obj.__annotations__['Archetypes.storage.AnnotationStorage-file'].setFilename(obj.getId())

def setLocalRolesBlock(obj, value):
    obj.__ac_local_roles_block__ = value
    obj.reindexObjectSecurity()

def fix_resolve_uids(obj, options):

    def xpath_query(node_names):
        if not isinstance(node_names, (list, tuple)):
            raise TypeError('"node_names" must be a list or tuple (not %s)' % type(node_names))
        return './/*[%s]' % ' or '.join(['name()="%s"' % name for name in node_names])

    html = obj.getRawText()
    if not isinstance(html, unicode):
        html = unicode(html, 'utf-8')
    try:
        root = lxml.html.fromstring(html)
    except:
        return

    for node in root.xpath(xpath_query(('img', 'a'))):
        url = ''
        if node.tag == 'img':
            url = node.attrib.get('src', '')
        elif node.tag == 'a':
            url = node.attrib.get('href', '')

        if url.startswith('resolveuid'):
            old_uid = url.split('/')[1]
            pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
            if os.path.exists(pickle_filename):
                old_data = cPickle.load(open(pickle_filename))
                old_path = old_data['metadata']['path']
                new_obj = obj.restrictedTraverse(old_path, None)
                if new_obj is not None:
                    new_uid = new_obj.UID()
                    url_f = url.split('/')
                    url_f[1] = new_uid
                    url = '/'.join(url_f)
                    if node.tag == 'img':
                        node.attrib['src'] = url
                    elif node.tag == 'a':
                        node.attrib['href'] = url

    html = lxml.html.tostring(root, encoding=unicode)
    obj.setText(html)


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
            try:
                field.set(new_obj, v)
            except Exception, e:
                log('Could not update field %s of %s (error=%s)' % (field.getName(), new_obj.absolute_url(), e))

    setLocalRolesBlock(new_obj, obj_data['metadata']['local_roles_block'])
    setObjectPosition(new_obj, obj_data['metadata']['position_parent'])
    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
    setWFPolicy(new_obj, obj_data['metadata']['wf_policy'])
    setExcludeFromNav(new_obj, options)
    setContentType(new_obj, obj_data['metadata']['content_type'])
    new_obj.reindexObject()

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


    if portal_type_ not in ('ETGeoLocation', 'PraxisBericht', 'Projektdarstellung'):
        return

    if candidate is None or (candidate is not None and candidate.portal_type != portal_type_):
        try:
            constrainsMode = folder.getConstrainTypesMode()
        except AttributeError:
            constrainsMode = None
        if constrainsMode is not None:
            folder.setConstrainTypesMode(0)
        pt = obj_data['metadata']['portal_type']
        if not id_ in folder.objectIds():
            target_portal_type = target_pt(pt, id_, id_)
            try:
                folder.invokeFactory(target_portal_type, id=id_)
            except:
                id_ = id_ + '-2'
                folder.invokeFactory(target_portal_type, id=id_)
            if constrainsMode is not None:
                folder.setConstrainTypesMode(constrainsMode)
        new_obj = folder[id_]
    else:
        new_obj = candidate

    for k,v in obj_data['schemadata'].items():

        if k in ('title', 
                'description', 
                'remote_url',
                'location',
                'event_url',
                'subject',
                'contact_email', 
                'contact_phone',
                'contact_name'):
            setattr(new_obj, k, v)
            continue

        if k in ('text',):
            setattr(new_obj, k, RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html'))
            continue

        if k in ('image', 'file', 'projekt_foto', 'projekt_banner'):
            filename = '/'.join(v.split('/')[-3:])
            filename = os.path.join(options.input_directory, '..', filename)
            if os.path.exists(filename):
                v = open(filename, 'rb').read()
                mt = magic.from_buffer(v, True)
                ext = mt.split('/')[-1]
                filename = u'{}.{}'.format(new_obj.getId(), ext)
                if new_obj.portal_type == 'Image':
                    setattr(new_obj, k, namedfile.NamedBlobImage(v, filename=filename))
                    continue
                elif new_obj.portal_type == 'File':
                    setattr(new_obj, k, namedfile.NamedBlobFile(v, filename=filename))
                    continue
                elif new_obj.portal_type == 'eteaching.policy.experiencereport':
                    if k == 'projekt_foto':
                        new_obj.image = namedfile.NamedBlobFile(v, filename=filename)
                        continue
                    if k == 'projekt_banner':
                        new_obj.thumbnail = namedfile.NamedBlobFile(v, filename=filename)
                        continue

            else:
                log('No .bin file found %s' % filename)
                import pdb; pdb.set_trace() 
                continue

        if portal_type_ == 'Projektdarstellung':
            if k == 'projektTeam':
                new_obj.team = v
                continue
            if k == 'projektstart' and v:
                new_obj.start = v.asdatetime()
                continue
            if k == 'projektend' and v:
                new_obj.end = v.asdatetime()
                continue
            if k == 'url':
                if not v.startswith('http'):
                    v = 'http://' + v
                new_obj.url = v
                continue
            if k == 'langbeschreibung':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'fachbereich':
                new_obj.faculty = [MAP_FACULTY[x] for x in v]
                continue
            if k == 'kategorie':
                new_obj.category = MAP_CATEGORY.get(v)
                continue

        if portal_type_ == 'PraxisBericht':
            if k == 'anmoderation':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue

            if k == 'PDFBericht':
                new_obj.invokeFactory('eteaching.policy.mediadocument', id='bericht')
                bericht = new_obj['bericht']
                bericht.title = u'Bericht'
                bericht.display_title = u'Bericht'
                bericht.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                bericht.reindexObject()
                intid_util = getUtility(IIntIds)
                bericht_intid = intid_util.getId(bericht)
                new_obj.media_documents = [bericht_intid]


        if portal_type_ == 'ETGeoLocation':
            if k == 'geoBreite':
                new_obj.lat = v
                continue
            if k == 'geoBundesland':
                new_obj.state= v
                continue
            if k == 'geoCountryCode':
                new_obj.country = v
                continue
            if k == 'geoLaenge':
                new_obj.long = v
                continue
            if k == 'geoPlz':
                new_obj.postcode= v
                continue
            if k == 'geoStadt':
                new_obj.city = v
                continue
            if k == 'status':
                new_obj.university_status = [MAP_UNIVERSITY_STATUS[v]]
                continue
            if k == 'url':
                new_obj.url = v
                continue


        if portal_type_ == 'Medienbeitrag':

            if k in ('subtitle', 'partner'):
                setattr(new_obj, k, v)
                continue

            if k == 'media':
                id_ = v.split('/')[-1]
                id_ = id_.lower().replace('-', '_') # normalization
                id_ = id_.replace('__', '_')
                intid_util = getUtility(IIntIds)
                media_items = options.plone['media-items']
                if id_ in media_items.objectIds():
                    media_item_intid = intid_util.getId(media_items[id_])
                    new_obj.media = media_item_intid
                continue

        if k not in ('content_type',):
            print 'Unhandled: %s (%s) %s=%s' % (new_obj.absolute_url(), new_obj.portal_type, k, str(v)[:40])

    if portal_type_ == 'Event':
        from plone.app.event.dx.behaviors import IEventBasic
        start = obj_data['schemadata']['start']
        end = obj_data['schemadata']['end']
        if start:
            start = start.asdatetime()
            if end:
                end = end.asdatetime()
            tz = str(start.tzinfo)
            if tz.startswith('GMT'):
                tz = 'Etc/%s' % tz
            ev = IEventBasic(new_obj)
            if start:
                ev.start = start
            if end:
                ev.end = end
            ev.timezone = tz
            data_postprocessing(new_obj, None)


#    setLocalRolesBlock(new_obj, obj_data['metadata']['local_roles_block'])
    setObjectPosition(new_obj, obj_data['metadata']['position_parent'])
    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
#    setLayout(new_obj, obj_data['metadata']['layout'])
#    setWFPolicy(new_obj, obj_data['metadata']['wf_policy'])
    setExcludeFromNav(new_obj, options)
#    setContentType(new_obj, obj_data['metadata']['content_type'])
    new_obj.reindexObject()


def import_content(options):

    installed_products = [p['id'] for p in options.plone.portal_quickinstaller.listInstalledProducts()]

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

        new_obj = folder_create(options.plone, path, portal_type)
    
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

        current = options.plone.restrictedTraverse(path)

        for uid in uids:
            try:
                create_new_obj(options, current, uid)
            except ValueError as e:
                log('--> unknown content type %s' % CP.get(section, 'portal_type'))
        log('--> %d children created' % len(uids))

        if i % 10 == 0:
            transaction.savepoint()


def log(s):
    print >>sys.stdout, s


def fixup_uids(options):
    for brain in options.plone.portal_catalog({'portal_type' : ('Document', 'Page', 'News Item', 'ENLIssue')}):
        fix_resolve_uids(brain.getObject(), options)

def setup_plone(app, dest_folder, site_id, products=(), profiles=()):
    app = makerequest(app)
    dest = app
    if dest_folder:
        dest = dest.restrictedTraverse(dest_folder)
    if site_id in dest.objectIds():
        log('%s already exists in %s - REMOVING IT' % (site_id, dest.absolute_url(1)))
        if dest.meta_type != 'Folder':
            raise RuntimeError('Destination must be a Folder instance (found %s)' % dest.meta_type)
        dest.manage_delObjects([site_id])
    log('Creating new Plone site with extension profiles %s' % profiles)
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
#    import_members(options)
#    options.plone.restrictedTraverse('@@import-mediaitems')(u'file:///home/share/media')
#    import_groups(options)
#    import_placeful_workflow(options)
    import_content(options)
#    fixup_uids(options)
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

def main():
    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-x', '--extension-profiles', dest='extension_profiles', default='')
    parser.add_option('-i', '--input', dest='input_directory', default='')
    parser.add_option('-d', '--dest-folder', dest='dest_folder', default='sites')
    parser.add_option('-t', '--timestamp', dest='timestamp', action='store_true')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False)
    options, args = parser.parse_args(sys.argv[2:])
    import_site(options)

if __name__ == '__main__':
    main()

