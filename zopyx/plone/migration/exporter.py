################################################################
# Poor men's Plone export
# (C) 2013, ZOPYX Ltd, D-72074 Tuebingen
################################################################

###############################################################################
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
###############################################################################

import os
import uuid
import gc
import shutil
import sys
import cPickle
import transaction

from Acquisition import aq_inner
from Acquisition import aq_parent
from Testing.makerequest import makerequest
from OFS.interfaces import IOrderedContainer
from Products.CMFCore.WorkflowCore import WorkflowException
from AccessControl.SecurityManagement import newSecurityManager

# check for LinguaPlone
try:
    import Products.LinguaPlone  # noqa
    HAS_LINGUAPLONE = True
except ImportError:
    HAS_LINGUAPLONE = False

IGNORED_TYPES = (
    'NewsletterTheme',
)

IGNORED_IDS = (
    # IDs that are definitely not needed in Plone 4
    'portal_cache_settings',
)

PT_REPLACEMENT = {
    'Large Plone Folder': 'Folder',
}


def log(s):
    print >>sys.stdout, s


def export_plonegazette(options, newsletter):
    ini_fn = os.path.join(
        options.export_directory,
        '%s_plonegazette_subscribers' % _getUID(newsletter)
    )
    log('Exporting subscribers for %s to %s'
        % (newsletter.absolute_url(), ini_fn))
    fp = open(ini_fn, 'w')
    if 'subscribers' in newsletter.objectIds():
        sfolder = newsletter.subscribers
    elif 'subscribers' in newsletter.aq_parent.objectIds():
        sfolder = newsletter.aq_parent.subscribers
    else:
        sfolder = newsletter.aq_parent

    for i, subs in enumerate([
            sub for sub in sfolder.contentValues()
            if sub.portal_type == 'Subscriber'
    ]):
        if not subs.active:
            continue
        print >>fp, '[%d]' % i
        print >>fp, 'id = %s' % subs.getId()
        print >>fp, 'fullname = %s' % subs.Title()
        print >>fp, 'email = %s' % subs.Title()
        print >>fp, 'format = %s' % subs.format.lower()
    fp.close()
    log('Exported %d subscribers' % i)


def export_groups(options):

    log('Exporting groups')
    fp = open(os.path.join(options.export_directory, 'groups.ini'), 'w')
    acl_users = options.plone.acl_users
    if hasattr(acl_users, 'source_groups'):
        # yeah, its pas
        groups = acl_users.source_groups.getGroups()
    else:
        # omg, it could be gruf
        groups = acl_users.Groups.acl_users.getUsers()
    num_groups = len(groups)
    for i, group in enumerate(groups):
        if options.verbose:
            log('--> (%d/%d) %s' % ((i + 1), num_groups, group.getId()))
        print >>fp, '[%d]' % i
        print >>fp, 'name = %s' % group.getId()
        if not hasattr(group, 'getMemberIds'):
            members = [_.getId() for _ in
                       options.plone.getUsersInGroup(group.getId())]
        else:
            members = group.getMemberIds()
        print >>fp, 'members = %s' % ','.join(members)
        print >>fp, 'roles = %s' % ','.join(group.getRoles())

    fp.close()
    log('exported %d groups' % len(groups))


def export_members(options):

    log('Exporting Members')
    fp = open(os.path.join(options.export_directory, 'members.ini'), 'w')

    acl_users = options.plone.acl_users
    users = acl_users.getUserNames()
    num_users = len(users)
    pm = options.plone.portal_membership

    try:
        # Plone 2.5
        passwords = options.plone.acl_users.source_users._user_passwords
    except:
        # Plone 2.1
        passwords = None

    for i, username in enumerate(users):
        if username == "":
            # possibly Membrane User Object whick will be exported
            # later in structure_export
            continue
        user = acl_users.getUserById(username)
        member = pm.getMemberById(username)
        if member is None:
            if options.verbose:
                log('--> (%d/%d) INVALID %s' % ((i + 1), num_users, username))
            continue
        if options.verbose:
            log('--> (%d/%d) %s' % ((i + 1), num_users, username))
        roles = [
            r for r in member.getRoles()
            if r not in ('Member', 'Authenticated')
        ]
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


def newCounter():
    i = 0
    while True:
        yield i
        i += 1


def export_structure(options):

    def _export_structure(fp, context, counter):

        children = hasattr(context.aq_base, 'contentValues')\
            and context.contentValues()\
            or []
        children_uids = [_getUID(c) for c in children if _getUID(c)]
        context_uid = ''
        context_uid = _getUID(context)
        rel_path = _getRelativePath(context, options.plone)

        if options.verbose:
            log('--> Analyzing Structure: %s' % rel_path)

        print >>fp, '[%d]' % counter.next()
        print >>fp, 'id = %s' % context.getId()
        print >>fp, 'uid = %s' % context_uid
        print >>fp, 'path = %s' % rel_path
        print >>fp, 'portal_type = %s' % PT_REPLACEMENT.get(context.portal_type, context.portal_type)  # noqa
        print >>fp, 'default_page = %s' % _getDefaultPage(context)
        print >>fp, 'children_uids = %s' % ','.join(children_uids)
        print >>fp, 'parent_position = %d' % _getPositionInParent(context)
        print >>fp, 'local_roles_block = %d' % _getLocalRolesBlock(context)
        print >>fp
        for child in children:
            if child.getId() in IGNORED_IDS:
                if options.verbose:
                    log("    skipping ignored id '%s'" % child.getId())
                continue
            if child.portal_type in options.ignored_types:
                if options.verbose:
                    log("    skipping ignored portal_type '%s'"
                        % child.portal_type)
                continue
            if getattr(child.aq_inner, 'isPrincipiaFolderish', 0):
                _export_structure(fp, child, counter)

    log('Exporting structure')
    fp = open(os.path.join(options.export_directory, 'structure.ini'), 'w')
    _export_structure(fp, options.plone, newCounter())
    fp.close()


def _getLocalRolesBlock(obj):
    val = getattr(obj, '__ac_local_roles_block__', 0) or 0
    return int(val)


def _getReviewState(obj):
    try:
        return obj.portal_workflow.getInfoFor(obj, 'review_state')
    except WorkflowException:
        # log('Error retrieving review state for %s' % obj.absolute_url(1))
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
        result.append(dict(
            id=current.getId(),
            portal_type=PT_REPLACEMENT.get(
                current.portal_type, current.portal_type)
        ))
        current = current.aq_inner.aq_parent
    return list(reversed(result))


def _getRelativePath(obj, plone):
    plone_path = '/'.join(plone.getPhysicalPath())
    obj_path = '/'.join(obj.getPhysicalPath())
    return obj_path.replace(plone_path + '/', '')


def _getLayout(obj):
    return obj.getLayout() or obj.getDefaultLayout()


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
    ordered = IOrderedContainer(parent, None)
    if ordered is not None:
        pos = ordered.getObjectPosition(obj.getId())
    else:
        pos = 0
    return pos


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

    if 'portal_placeful_workflow' not in options.plone.objectIds():
        return

    export_dir = os.path.join(options.export_directory, 'placeful_workflow')
    os.mkdir(export_dir)
    pwt = options.plone.portal_placeful_workflow
    for id_ in pwt.objectIds():
        zexp = pwt.manage_exportObject(id_, download=1)
        zexp_name = os.path.join(export_dir, id_ + '.zexp')
        fp = open(zexp_name, 'wb')
        fp.write(zexp)
        fp.close()
        log('Exported PlacefulWorkflow %s to %s' % (id_, zexp_name))


def export_content(options):

    log('Exporting content')
    catalog = options.plone.portal_catalog

    export_dir = os.path.join(options.export_directory, 'content')

    if options.batch_start == 0:
        # only create initially
        os.mkdir(export_dir)
    if HAS_LINGUAPLONE:
        brains = catalog(Language="all")
    else:
        brains = catalog()
    log('%d items' % len(brains))

    errors = []
    num_exported = 0
    stats = {}

    num_brains = len(brains)
    bsize = options.batch_size
    bstart = options.batch_start
    if bsize:
        brains = brains[bstart:bstart + bsize]
    for i, brain in enumerate(brains):
        if brain.getId in IGNORED_IDS:
            if options.verbose:
                log("    skipping ignored id '%s'" % brain.getId)
            continue
        if brain.portal_type in options.ignored_types:
            if options.verbose:
                log("    skipping ignored portal_type '%s'"
                    % brain.portal_type)
            continue

        if options.verbose:
            log('--> (%d/%d) %s' % (i + bstart, num_brains, brain.getPath()))

        try:
            obj = brain.getObject()
        except Exception, e:
            try:
                obj = options.plone.unrestrictedTraverse(brain.getPath())
            except Exception, e:
                errors.append(dict(path=brain.getPath(), error=e))
                continue

        # content-type specific export code
        if obj.portal_type in ('Newsletter', 'NewsletterTheme'):
            export_plonegazette(options, obj)

        try:
            schema = obj.Schema()
        except AttributeError:
            errors.append(dict(path=brain.getPath(), error='no schema'))
            schema = None

        obj_data = dict(schemadata=dict(), metadata=dict())
        if schema:
            ext_filename = None
            for field in schema.fields():
                name = field.getName()
                try:
                    value = field.get(obj)
                except ValueError:
                    continue
                if field.type in ('image', 'file'):
                    ext_filename = os.path.join(
                        export_dir, '%s_%s.bin' % (_getUID(obj), name))
                    extfp = open(ext_filename, 'wb')
                    data = ''
                    try:
                        data = str(value.data)
                    except:
                        data = value
                    extfp.write(data)
                    #extfp.close()
                    f_close_sync(extfp)  # gc
                    del extfp  # gc
                    del data  # gc
                    value = 'file://%s/%s_%s.bin' % (
                        os.path.abspath(export_dir), _getUID(obj), name)
                elif field.type == 'reference':
                    value = field.getRaw(obj)
                if name == "language" and not value:
                    value = options.plone.portal_languages.getDefaultLanguage()
                obj_data['schemadata'][name] = value
                del value  # gc

        if obj.portal_type == 'Newsletter':
            obj_data['schemadata']['text'] = obj.text
            obj_data['schemadata']['id'] = obj.getId()

        obj_data['metadata']['id'] = obj.getId()
        obj_data['metadata']['uid'] = _getUID(obj)
        obj_data['metadata']['portal_type'] = PT_REPLACEMENT.get(obj.portal_type, obj.portal_type)  # noqa
        obj_data['metadata']['review_state'] = _getReviewState(obj)
        obj_data['metadata']['owner'] = obj.getOwner().getUserName()
        obj_data['metadata']['content_type'] = _getContentType(obj)
        obj_data['metadata']['text_format'] = _getTextFormat(obj)
        obj_data['metadata']['local_roles'] = obj.get_local_roles()
        obj_data['metadata']['parents'] = _getParents(obj)
        obj_data['metadata']['path'] = _getRelativePath(obj, options.plone)
        obj_data['metadata']['layout'] = _getLayout(obj)
        obj_data['metadata']['wf_policy'] = _getWFPolicy(obj)
        obj_data['metadata']['default_page'] = _getDefaultPage(obj)
        obj_data['metadata']['position_parent'] = _getPositionInParent(obj)
        obj_data['metadata']['local_roles_block'] = _getLocalRolesBlock(obj)

        if obj.portal_type not in stats:
            stats[obj.portal_type] = 0
        stats[obj.portal_type] += 1
        num_exported += 1

        try:
            related_items = ','.join([o.UID() for o in obj.getRelatedItems()])
            related_items_paths = ','.join([
                _getRelativePath(o, options.plone)
                for o in obj.getRelatedItems()
            ])
        except AttributeError:
            related_items = ''
            related_items_paths = ''

        if HAS_LINGUAPLONE and obj.isCanonical():
            obj_data['translations'] = {}
            for lang, tdata in obj.getTranslations().items():
                if not lang or tdata[0] is obj:
                    continue
                obj_data['translations'][lang] = _getRelativePath(
                    tdata[0],
                    options.plone
                )

        if obj.portal_type == "Topic":
            obj_data['metadata']['topic_criterions'] = ','.join(obj.objectIds())  # noqa
            obj_data['topic_criterions'] = dict()
            for crit in obj.objectValues():
                try:
                    schema = crit.aq_base.Schema()
                except AttributeError:
                    continue
                crit_id = crit.getId()
                obj_data['topic_criterions'][crit_id] = dict()
                for field in schema.fields():
                    name = field.getName()
                    if field.type == 'reference':
                        value = field.getRaw(crit)
                    else:
                        value = field.get(crit)
                    obj_data['topic_criterions'][crit_id][name] = value
                obj_data['topic_criterions'][crit_id]['portal_type'] = crit.portal_type  # noqa
                obj_data['topic_criterions'][crit_id]['path'] = _getRelativePath(crit, options.plone)  # noqa

        # write to INI file
        fp = open(os.path.join(options.export_directory, 'content.ini'), 'a')
        print >>fp, '[%s]' % _getUID(obj)
        print >>fp, 'path = %s' % _getRelativePath(obj, options.plone)
        print >>fp, 'id = %s' % obj.getId()
        print >>fp, 'portal_type = %s' % obj.portal_type
        print >>fp, 'uid = %s' % _getUID(obj)
        print >>fp, 'related_items = %s' % related_items
        print >>fp, 'related_items_paths = %s' % related_items_paths
        print >>fp, 'layout = %s' % obj_data['metadata']['layout']
        print >>fp, 'default_page = %s' % obj_data['metadata']['default_page']
        print >>fp, 'wf_policy = %s' % obj_data['metadata']['wf_policy']
        print >>fp, 'owner = %s' % obj_data['metadata']['owner']
        print >>fp, 'creators = %s' % ','.join(obj_data['schemadata'].get('creators', ''))  # noqa
        print >>fp, 'position_parent = %d' % obj_data['metadata']['position_parent']  # noqa
        print >>fp, 'local_roles_block = %d' % obj_data['metadata']['local_roles_block']  # noqa
        if obj.portal_type == "Topic":
            print >>fp, 'topic_criterions = %s' % obj_data['metadata']['topic_criterions']  # noqa
        print >>fp
        #fp.close()
        f_close_sync(fp)  # gc
        del fp  # gc

        # dump data as pickle
        pickle_name = os.path.join(export_dir, _getUID(obj))
        pickle_file = open(pickle_name, 'wb')
        try:
            cPickle.dump(obj_data, pickle_file)
        except Exception, msg:
            log("%s: %s (%s)" % (Exception, msg, obj_data))
        #pickle_file.close()
        f_close_sync(pickle_file)  # gc
        del pickle_file  # gc

        value = None
        del value

        obj_data = None
        del obj_data

        obj = None
        del obj

    if errors:
        log('Errors')
        for e in errors:
            log(e)

    log('Stats')
    log('%d items exported' % num_exported)
    for k in sorted(stats.keys()):
        log('%-40s %d' % (k, stats[k]))


def f_close_sync(fp):
    fp.flush()
    os.fsync(fp.fileno())
    fp = None


def export_site(app, options):

    plone = app.unrestrictedTraverse(options.path, None)
    if plone is None:
        raise RuntimeError('Plone site not found (%s)' % options.path)

    site_id = plone.getId()
    export_dir = os.path.join(options.output, site_id)
    if os.path.exists(export_dir) and options.batch_start == 0:
        # only delete/create initially
        try:
            shutil.rmtree(export_dir)
        except:
            log('Error in removing existing export directory %s.\n'
                'You have to remove it manually' % export_dir)
            return
    if options.batch_start == 0:
        os.makedirs(export_dir)

    log('Exporting Plone site: %s' % options.path)
    log('Export directory:  %s' % os.path.abspath(export_dir))

    # app = Zope.app()
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
    if options.batch_start == 0:
        # only do these exports, when we don't batch or on a starting batch
        export_groups(options)
        export_members(options)
        export_placeful_workflow(options)
        export_structure(options)
    export_content(options)

    log('Export done...releasing memory und Tschuessn')


def main():
    from optparse import OptionParser
    import Zope
    gc.enable()
    app = Zope.app()
    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-p', '--path', dest='path', default='')
    parser.add_option('-o', '--output', dest='output', default='')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      default=False)
    parser.add_option('-i', '--ignore', dest='ignored_types',
                      action='store', default=IGNORED_TYPES,
                      help="Provide comma separated List of Portal Types "
                      "to ignore")
    parser.add_option('-b', '--batch_size', dest='batch_size', default=0)
    parser.add_option('-s', '--batch_start', dest='batch_start', default=0)
    options, args = parser.parse_args()
    options.app = app
    if isinstance(options.ignored_types, basestring):
        options.ignored_types = options.ignored_types.split(',')
    options.batch_start = int(options.batch_start)
    options.batch_size = int(options.batch_size)
    export_site(app, options)
    transaction.commit()

if __name__ == '__main__':
    main()
