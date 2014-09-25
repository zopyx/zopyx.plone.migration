# -*- coding: utf8 -*-


################################################################
# Poor men's Plone export
# (C) 2013, ZOPYX Ltd, D-72074 Tuebingen
################################################################

import pytz
import time
import json
import os
import plone.api
import datetime
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
from plone.app.event.dx.behaviors import IEventBasic
from plone import namedfile
from plone.app.textfield.value import RichTextValue
from plone.app.event.dx.behaviors import data_postprocessing
from zope.intid.interfaces import IIntIds

import sys


IGNORED_FIELDS = ('id', 'relatedItems')

# OK
MAP_UNIVERSITY_STATUS = {
    'Uni': 'university',
    'Fachhochschule': 'college',
    'Kunst- und Musikhochschule': 'academy_of_arts',
    'Hochschulverbund': 'university_partnership',
    'Forschungseinrichtung': 'research_institute',
    'Vorgeschlagene Forschungseinrichtung': 'suggested_research_institute',
    'Sonstiges (Kein besonderer Ort)': 'other',
}
# OK
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

# OK
MAP_CATEGORY = {
    'Lernumgebung':                 'learning_environment',
    'Lernmaterial':      'learning_material',
    'Lernmaterial(-sammlung)':      'learning_material',
    'Software':                     'software',
    'Lehr-/Lernszenario':           'learning_scenario'
}

# OK 
MAP_ONLINE_EVENT_STATUS_VOCABULARY = {
        'zukuenftig': 'future',
        'live': 'live',
        'vergangen': 'past'}

# OK
MAP_ONLINE_EVENT_TYPE_VOCABULARY = {
        'Chat': 'chat',
        'Ringvorlesung': 'lecture',
        'Schulung': 'training',
        'Workshop': 'workshop' }


# OK
MAP_REFERENCE_EXAMPLE_USE_OF_MEDIA_TAGS = {
        'Hypertext': 'hypertext',
        'PDF': 'pdf',
        'Chat': 'chat',
        'Newsgroup': 'newsgroup',
        'Shared Workspace': 'shared_workspace',
        'Application Sharing': 'application_sharing',
        'Simulation': 'simulation',
        'Animation': 'animation',
        'Videokonferenz': 'video_conference',
        'Videoübertragung/-aufzeichnung': 'video_streaming_recording',
        'Audiokonferenz': 'audio_conference',
        'Audioübertragung/-aufzeichnung': 'audio_streaming_recording',
        'E-Mail': 'email',
        'CBT / WBT': 'cbt_wbt',
        'LMS / Lernmanagementsysteme': 'lms',
        'Sonstige': 'other'
        }


# OK
MAP_REFERENCE_EXAMPLE_LEARNING_SCENARIO_TAGS = {
        'Vorlesung': 'lecture',
        'Übung': 'exercise',
        'Tutorium': 'tutorial',
        'Praktikum': 'internship',
        'Projekt': 'project',
        'Seminar': 'seminar',
        'Betreuung': 'support',
        'Übergreifend / Sonstige': 'comprehensive',
        }

# OK
MAP_REFERENCE_EXAMPLE_GLOBAL_FACULTY_TAGS = {
        'Agrar- und Forstwissenschaft': 'agrarian_economy',
        'Geistes- und Sozialwissenschaften': 'humanities',
        'Geowissenschaft': 'geosciences',
        'Informatik': 'informatics',
        'Ingenieurswissenschaften': 'engineering',
        'Kunst, Design und Medienwissenschaft': 'media_studies',
        'Medizin und Gesundheitswesen': 'medical_science',
        'Naturwissenschaft und Mathematik': 'natural_science',
        'Rechtswissenschaft': 'law',
        'Sportwissenschaft': 'sport_science',
        'Sprachen und Sprachwissenschaft': 'linguistics',
        'Wirtschaftswissenschaften': 'economic_sciences',
        'Sonstiges': 'other'
        }

# OK
MAP_REFERENCE_EXAMPLE_GLOBAL_CATEGORY_TAGS = {
        'Lernumgebung': 'learning_environment',
        'Lernmaterial(-sammlung)': 'learning_material',
        'Software': 'software',
        'Lehr-/Lernszenario': 'learning_scenario',
        }


# OK
MAP_REFERENCE_EXAMPLE_LEARNING_GOAL_TAGS = {
        'Informationsvermittlung': 'information_transfer',
        'Wissenserarbeitung': 'studying_knowledge',
        'Üben u. Anwenden': 'practice',
        'Wissenstransfer': 'transfer_of_knowledge',
        'Diskussion u. Austausch': 'discussion',
        'Motivation': 'motivation',
        'Feedback u. Lernerfolgskontrolle': 'feedback',
        'Sonstige': 'other'
        }

# OK
MAP_PROJECT_GLOBAL_FACULTY_TAGS = {
        'Agrar- und Forstwissenschaft': 'agrarian_economy',
        'Geistes- und Sozialwissenschaften': 'humanities',
        'Geowissenschaft': 'geosciences',
        'Informatik': 'informatics',
        'Ingenieurswissenschaften': 'engineering',
        'Kunst, Design und Medienwissenschaft': 'media_studies',
        'Medizin und Gesundheitswesen': 'medical_science',
        'Naturwissenschaft und Mathematik': 'natural_science',
        'Rechtswissenschaft': 'law',
        'Sportwissenschaft': 'sport_science',
        'Sprachen und Sprachwissenschaft': 'linguistics',
        'Wirtschaftswissenschaften': 'economic_sciences',
        'Sonstiges': 'other'
        }

# OK
MAP_PROJECT_GLOBAL_CATEGORY_TAGS = {
        'Lernumgebung': 'learning_environment',
        'Lernmaterial(-sammlung)': 'learning_material',
        'Software': 'software',
        'Lehr-/Lernszenario': 'learning_scenario',
        }


# OK
MAP_LITERATURE_TYPE_OF_PUBLICATION_TAGS = {
        'Audiovisuelles Medium': 'audiovisual',
        'Dissertation': 'dissertation',
        'Elektronische Zeitschrift': 'e_journal',
        'Forschungsbericht': 'research_paper',
        'Monographie': 'monograph',
        'Onlinequelle': 'online_source',
        'Positionspapier': 'position_paper',
        'Pressemitteilung': 'press_release',
        'Sammelband': 'anthology',
        'Sammelbandbeitrag': 'anthology_essays',
        'Tageszeitung': 'newspaper',
        'Tagungsbeitrag': 'conference_contribution',
        'Zeitschrift': 'journal',
        'Zeitschriftenbeitrag': 'journal_article'
        }


# OK
MAP_TEST_REPORT_CATEGORY_TAGS = {
        'HTML': 'html',
        'PDF': 'pdf',
        'Bild': 'image',
        'Audio': 'audio',
        'Video': 'video',
        'Animation': 'animation',
        'Simulation': 'simulation',
        'CBT/WBT': 'cbt_wbt',
        'CMS': 'cms',
        'Synchrone Kommunikation': 'synchronous_communication',
        'Asynchrone Kommunikation': 'asynchronous_communication',
        'Kooperation': 'cooperation',
        'Präsentation': 'presentation',
        'LMS': 'lms',
        'Aufzeichnung': 'recording',
        'Literaturverwaltung': 'literature_management',
        'Sonstiges': 'other',
        }

# OK
MAP_TEST_REPORT_SUPPORTED_OS_TAGS = {
        'Windows': 'windows',
        'Macintosh': 'macintosh',
        'Unix / Linux': 'unix',
        'Sonstiges': 'other',
        }


# OK
USERDATASCHEMA_POSITION_TAGS = {
        'lehrender': 'teacher',
        'forscher': 'researcher',
        'berater': 'consultant',
        'mitarbeiter': 'university_staff',
        'doktorand': 'doctoral_candidate',
        'tutor': 'tutor',
        'student': 'student',
        }
# OK
USERDATASCHEMA_ACADEMIC_TAGS = {
        'prof': 'professor',
        'dr': 'doctor',
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

        if 'RRuuleZz' in username:  # spammer
            continue


        if not options.plone.acl_users.getUser(username):

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
                    username_normalized = unicode(username, 'utf8', 'ignore').encode('ascii', 'ignore')
                    plone.api.user.create(email=get(section, 'email'),
                                          username=username_normalized,
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

        vcard = json.loads(get(section, 'vcard'))
        member_props = dict(email=get(section, 'email'),
                            fullname=get(section, 'fullname'))

        print '-'*80
        import pprint
        pprint.pprint(vcard)

        def to_unicode(s):
            if not isinstance(s, unicode):
                return unicode(s or '', 'utf8', 'ignore')
            return s
        
        # textish properties
        member_props['firstname'] = to_unicode(vcard.get('vorname', ''))
        member_props['lastname'] = to_unicode(vcard.get('name', ''))
        member_props['gender'] = to_unicode(vcard.get('geschlecht', ''))
        member_props['position'] = USERDATASCHEMA_POSITION_TAGS.get(to_unicode(vcard.get('position', '')))
        member_props['academic'] = USERDATASCHEMA_ACADEMIC_TAGS.get(to_unicode(vcard.get('academic', '')))
        member_props['phone'] = to_unicode(vcard.get('fon1', ''))
        member_props['cv'] = to_unicode(vcard.get('bemerkung', ''))

        # datetime
        v = vcard.get('geburtstag')
        if v:
            member_props['birthday'] = v

        # list properties
        member_props['specialties'] = '\n'.join([t.strip() for t in (vcard.get('fachgebiete') or '').split(',') if t.strip()])
        member_props['expertise'] =   '\n'.join([t.strip() for t in (vcard.get('expertise') or '').split(',') if t.strip()])
        member_props['memberships'] = '\n'.join([t.strip() for t in (vcard.get('mitgliedschaften') or '').split(',') if t.strip()])

#        member_props['projects'] =    [t for t in (vcard.get('projekte') or '').split(',') if t]
#        member_props['db_projects'] = vcard.get('db_projekte', [])

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

    if default_portal_type in ('Weiterbildung', 'Veranstaltung'):
        return 'Event'

    if default_portal_type in ('ETEvent',):
        return 'eteaching.policy.onlineevent'

    if default_portal_type in ('Steckbrief',):
        return 'eteaching.policy.testreport'

    if default_portal_type in ('Partition',):
        return 'Partition'

    if default_portal_type=='ThemenSpecial':
        return 'eteaching.policy.special'

    if default_portal_type=='Literatur':
        return 'eteaching.policy.literature'

    if default_portal_type=='Glossar':
        return 'eteaching.policy.glossaryterm'
    
    if default_portal_type=='Referenzbeispiel':
        return 'eteaching.policy.referenceexample'

    if default_portal_type=='Hochschulinfo':
        return 'eteaching.policy.location'

    if default_portal_type=='Medienbeitrag':
        return 'eteaching.policy.podcastitem'

    if default_portal_type == 'ETGeoLocation':
        return 'eteaching.policy.location'

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


def setModificationDate(obj, modified):
    obj.setModificationDate(modified)


def setCreationDate(obj, created):
    obj.creation_date = created


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

    try:
        html = obj.getRawText()
    except AttributeError:
        print 'Unable to fix uuids for %s %s' % (obj.absolute_url(), obj.portal_type)
        return
   
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

    if state_id == 'visible':
        state_id = 'published'
        content.setExpirationDate(DateTime() - 1)

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

    setModificationDate(new_obj, obj_data['metadata']['modified'])
    setCreationDate(new_obj, obj_data['metadata']['created'])
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

    if options.portal_types:
        allowed_types = options.portal_types.split(',')
        allowed_types = [t.strip() for t in allowed_types]
        if portal_type_ not in allowed_types:
            return

#    if portal_type_ not in ('Veranstaltung', 'Weiterbildung'):
#        return

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

        if k in ('image', 'file', 'projekt_foto', 'projekt_banner', 'hslogo', 'screenshot', 'logo', 'themengrafik', 'event_foto', 'event_foto_sw'):
            filename = '/'.join(v.split('/')[-3:])
            filename = os.path.join(options.input_directory, '..', filename)
            if os.path.exists(filename):
                v = open(filename, 'rb').read()
                mt = magic.from_buffer(v, True)
                ext = mt.split('/')[-1]
                filename = u'{}.{}'.format(new_obj.getId(), ext)
                contentType = mt
                if new_obj.portal_type == 'Image':
                    setattr(new_obj, k, namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType))
                    continue
                elif new_obj.portal_type == 'File':
                    setattr(new_obj, k, namedfile.NamedBlobFile(v, filename=unicode(filename), contentType=contentType))
                    continue
                elif new_obj.portal_type == 'eteaching.policy.experiencereport':
                    if k == 'projekt_foto':
                        new_obj.image = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                    if k == 'projekt_banner':
                        new_obj.thumbnail = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                elif new_obj.portal_type == 'eteaching.policy.location':
                    if k == 'hslogo':
                        new_obj.image = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                elif new_obj.portal_type == 'eteaching.policy.referenceexample':
                    if k == 'screenshot':
                        new_obj.image = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                elif new_obj.portal_type == 'eteaching.policy.testreport':
                    if k == 'logo':
                        new_obj.logo = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                    if k == 'screenshot':
                        new_obj.screenshot = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                elif new_obj.portal_type == 'eteaching.policy.special':
                    if k == 'themengrafik':
                        new_obj.image = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                elif new_obj.portal_type == 'eteaching.policy.partition':
                    if k == 'image':
                        new_obj.image = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                elif new_obj.portal_type == 'eteaching.policy.onlineevent':
                    if k == 'event_foto':
                        new_obj.image = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue
                    if k == 'event_foto_sw':
                        new_obj.thumbnail = namedfile.NamedBlobImage(v, filename=unicode(filename), contentType=contentType)
                        continue

            else:
                log('No .bin file found %s' % filename)
                import pdb; pdb.set_trace() 
                continue

        if portal_type_ == 'Glossar':
            if k == 'body':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue

        if portal_type_ == 'Steckbrief':
            _map = { 'produktbeschreibung': 'text',
                    'vorteile': 'pros',
                    'nachteile': 'cons',
                    'beispiele': 'examples',
                    'formate': 'file_formats',
                    'getestete version': 'tested_version',
                    'hersteller': 'producer',
                    'preis': 'price',
                    'windows': 'windows',
                    'macintosh': 'macintosh',
                    'unix': 'unix',
                    'sonstige plattform': 'other_os',
                    'weitere anforderungen': 'requirements',
                    'einstiegslevel': 'entry_level',
                    'tutorials': 'tutorials',
                    'hinweise': 'hints',
                    'alternativen': 'alternatives', }

            if k in _map:
                setattr(new_obj, _map[k], RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html'))
                continue

            if k == 'plattform':
                new_obj.supported_os = [MAP_TEST_REPORT_SUPPORTED_OS_TAGS.get(k)  for k in v]
                continue
            if k == 'produktkategorie':
                new_obj.category = [MAP_TEST_REPORT_CATEGORY_TAGS.get(k)  for k in v]
                continue

        if portal_type_ == 'Projektdarstellung':
            if k == 'kurzbeschreibung':
                new_obj.description = v
                continue
            if k == 'projektTeam':
                new_obj.team = v
                continue
            if k == 'projektstart' and v:
                new_obj.start = datetime(v.year(), v. month(), v.day())
                continue
            if k == 'projektende' and v:
                new_obj.end = datetime(v.year(), v. month(), v.day())
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
                new_obj.faculty = [MAP_PROJECT_GLOBAL_FACULTY_TAGS[x] for x in v]
                continue
            if k == 'kategorie':
                new_obj.category = [MAP_PROJECT_GLOBAL_CATEGORY_TAGS.get(v)]
                continue

        if portal_type_ == 'PraxisBericht':
            if k == 'anmoderation':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue

            if k == 'PDFBericht':
                new_obj.invokeFactory('eteaching.policy.mediadocument', id='bericht')
                bericht = new_obj['bericht']
                bericht.title = u'Bericht'
                bericht.display_title = True
                bericht.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                bericht.portal_workflow.doActionFor(bericht, 'publish')
                bericht.reindexObject()
                intid_util = getUtility(IIntIds)
                bericht_intid = intid_util.getId(bericht)
                new_obj.media_documents = [bericht_intid]

        if portal_type_ == 'Hochschulinfo':
            if k == 'elearn_url':
                new_obj.elearning_url = v
                continue
            if k == 'news_feed_url':
                new_obj.news_feed_url = v
                continue
            if k == 'selbstdarstellung':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'url':
                new_obj.url = v
                continue

        if portal_type_ == 'ThemenSpecial':
            if k == 'intro_text':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue

        if portal_type_ == 'Literatur':
            if k == 'publikationsautor':
                new_obj.author = v
                continue
            if k == 'publikationstitel':
                new_obj.title_of_publication = v
                continue
            if k == 'publikationsdatum':
                new_obj.year = v
                continue
            if k == 'publikationsort':
                new_obj.place_of_publication = v
                continue
            if k == 'publikationstyp':
                new_obj.type_of_publication = MAP_LITERATURE_TYPE_OF_PUBLICATION_TAGS.get(v)
                continue
            if k == 'url':
                new_obj.url = v
                continue
            if k == 'visited':
                new_obj.visited = v
                continue

        if portal_type == 'Partition':
            if k == 'body':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue

        if portal_type_ == 'Referenzbeispiel':
            if k == 'langtitel':
                new_obj.description = v
                continue
            if k == 'medieneinsatz':
                new_obj.use_of_media = [MAP_REFERENCE_EXAMPLE_USE_OF_MEDIA_TAGS.get(k) for k in v]
                continue
            if k == 'lehrszenario':
                new_obj.learning_scenario = [MAP_REFERENCE_EXAMPLE_LEARNING_SCENARIO_TAGS.get(k) for k in v]
                continue
            if k == 'fachbereichNeu':
                new_obj.faculty = [MAP_PROJECT_GLOBAL_FACULTY_TAGS[x] for x in v]
                continue
            if k == 'kategorie':
                new_obj.category = [MAP_PROJECT_GLOBAL_CATEGORY_TAGS.get(v)]
                continue
            if k == 'lehrfunktion':
                new_obj.learning_goal = [MAP_REFERENCE_EXAMPLE_LEARNING_GOAL_TAGS.get(k) for k in v]
                continue
            if k == 'kurzbeschreibung':
                new_obj.text = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'url':
                new_obj.url = v
                continue
            if k == 'ansprechpartner':
                new_obj.contact = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'zielgruppe':
                new_obj.audience = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'ziele und inhalte':
                new_obj.aims = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'didaktisches konzept':
                new_obj.concept = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'curriculare verankerung':
                new_obj.anchorage = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'beteilungen und kooperationen':
                new_obj.participations = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'ergebnisse':
                new_obj.results = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'zeitraum':
                new_obj.period = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'foerderung':
                new_obj.support = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'kosten':
                new_obj.cost = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'rahmenbedingungen':
                new_obj.environment = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'technik':
                new_obj.technology = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue

        if portal_type_ == 'ETEvent':
            if k == 'status':
                new_obj.status = MAP_ONLINE_EVENT_STATUS_VOCABULARY.get(v)
                continue
            if k == 'typ':
                new_obj.type = MAP_ONLINE_EVENT_TYPE_VOCABULARY.get(v)
                continue
            if k == 'datum':
                if v:
                    new_obj.start = datetime(v.year(), v. month(), v.day(), v.hour(), v.minute(), int(v.second()))
                continue
            if k == 'experte':
                new_obj.expert = v
                continue
            if k == 'beschreibung':
                new_obj.text_future = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'kurzbeschreibung_vergangen':
                new_obj.text_past = RichTextValue(unicode(v, 'utf-8'), 'text/html', 'text/html')
                continue
            if k == 'kurzbeschreibung_zukunft':
                new_obj.description = v
                continue
            if k == 'link_event':
                new_obj.link_event = v
                continue
            if k == 'code_schnipsel':
                new_obj.code_snippets = v
                continue
            if k == 'folien':
                new_obj.slides = [dict(name=item.split(';')[0], link=item.split(';')[1]) for item in v]
                continue

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
                new_obj.university_status = MAP_UNIVERSITY_STATUS[v]
                continue
            if k == 'url':
                new_obj.url = v
                continue

        if portal_type_ == 'Weiterbildung':

            if k == 'Kurzbeschreibung':
                new_obj.description = v
                continue
            if k == 'Veranstaltungsbeginn':
                if v:
                    ev = IEventBasic(new_obj)
                    ev.start = datetime.now()
                    ev.end= datetime.now()
                    ev.timezone = 'UTC'
                    if v:
                        ev.start = datetime(v.year(), v. month(), v.day())

                        end = obj_data['schemadata']['Veranstaltungsende']
                        if end:
                            ev.end = datetime(end.year(), end.month(), end.day())
                continue
            if k == 'Veranstaltungsform':
                new_obj.form_of_event = v
                continue
            if k == 'Ort':
                new_obj.location = v
                continue
            if k == 'Ansprechpartner':
                new_obj.contact_name = v
                continue
            if k == 'EMail':
                new_obj.contact_email = v
                continue
            if k == 'VeranstaltungsURL':
                new_obj.event_url = v
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

    if portal_type_ == 'Weiterbildung':
        data_postprocessing(new_obj, None)

#    setLocalRolesBlock(new_obj, obj_data['metadata']['local_roles_block'])
    setModificationDate(new_obj, obj_data['metadata']['modified'])
    setCreationDate(new_obj, obj_data['metadata']['created'])
    setObjectPosition(new_obj, obj_data['metadata']['position_parent'])
    changeOwner(new_obj, obj_data['metadata']['owner'])
    setLocalRoles(new_obj, obj_data['metadata']['local_roles'])
    setReviewState(new_obj, obj_data['metadata']['review_state'])
#    setLayout(new_obj, obj_data['metadata']['layout'])
#    setWFPolicy(new_obj, obj_data['metadata']['wf_policy'])
    setExcludeFromNav(new_obj, options)
#    setContentType(new_obj, obj_data['metadata']['content_type'])
    new_obj.reindexObject()

def fixup_geolocation(options):

    structure_ini = os.path.join(options.input_directory, 'content.ini')
    CP = ConfigParser()
    CP.read([structure_ini])
    get = CP.get

    sections = CP.sections()

    # Now recreate the child objects within
    log('Fixup geolocation')
    for i, section in enumerate(sections):
        portal_type = CP.get(section, 'portal_type')
        if portal_type in ('Projektdarstellung', 'PraxisBericht'):
            path_ = CP.get(section, 'path')
            obj = options.plone.restrictedTraverse(path_, None)
            if obj is None:
                continue
            old_uid = CP.get(section, 'uid')
            pickle_filename = os.path.join(options.input_directory, 'content', old_uid)
            obj_data = cPickle.load(file(pickle_filename))
            schemadata = obj_data['schemadata']
            institutsLocation = schemadata['institutsLocation']
            brains = options.plone.portal_catalog(getId=institutsLocation)
            intid_util = getUtility(IIntIds)
            if brains:
                geo_id  = intid_util.getId(brains[0].getObject())
                obj.location_reference = [geo_id]
            else:
                print 'no GEO object found {}'.format(institutsLocation)


    transaction.savepoint()

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

def import_blog_entries(options):

    print 'Importing blog entries'
    view = options.plone.restrictedTraverse('@@import-blogentries')
    view('/home/people/ajung/blog_dump.xml')
         
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
    if options.import_members:
        import_members(options)
    options.plone.restrictedTraverse('@@import-mediaitems')(u'file:///home/share/media')
    import_groups(options)
#    import_placeful_workflow(options)
#    import_content(options)
##    import_blog_entries(options)
#    fixup_geolocation(options)
#    fixup_uids(options)

#    options.plone.restrictedTraverse('@@rebuild-backreferences')()

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
    parser.add_option('-p', '--portal-types', dest='portal_types', default='')
    parser.add_option('-d', '--dest-folder', dest='dest_folder', default='sites')
    parser.add_option('-t', '--timestamp', dest='timestamp', action='store_true')
    parser.add_option('-m', '--import-members', dest='import_members', action='store_true')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true', default=False)
    options, args = parser.parse_args(sys.argv[2:])
    import_site(options)

if __name__ == '__main__':
    main()

