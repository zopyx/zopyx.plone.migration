################################################################
# Plone ini-style exporter
#
# Written by Andreas Jung
# (C) 2008, ZOPYX Ltd. & Co. KG, D-72070 Tuebingen
################################################################

import os
import shutil
import tempfile

handlers = dict()  # portal_type -> handler

def registerHandler(handler):
    portal_types = handler.portal_types
    if isinstance(portal_types, str):
        portal_types = [portal_types]
    for pt in portal_types:
        handlers[pt] = handler


def export_members(plone, export_dir, verbose):

    print 'Exporting Members'
    fp = file(os.path.join(export_dir, 'members.ini'), 'w')

    acl_users = plone.acl_users
    pm = plone.portal_membership

    try:
        # Plone 2.5
        passwords = plone.acl_users.source_users._user_passwords
    except:
        # Plone 2.1
        passwords = None

    members = plone.portal_membership.getMembersFolder()
    for username in acl_users.getUserNames():

        if not username in members.objectIds():
            continue

        # we are only interested in members with Anbieter items
        anbieter_objs = members[username].objectIds('Anbieter')
        if len(anbieter_objs) == 0:
            continue

        if verbose:
            print '-> %s' % username
        user = acl_users.getUserById(username)
        member = pm.getMemberById(username)
        if member is None:
            continue
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
        print >>fp
    fp.close()


class BaseHandler(object):

    portal_types = ()
    ident = None
    initialized = False

    def __init__(self, plone, export_dir='exports', verbose=False):
        self.plone = plone
        self.portal_id = plone.getId()
        self.portal_path = plone.absolute_url(1)
        self.export_dir = export_dir
        self.verbose = verbose
        fname = os.path.join(export_dir, self.ident + '.ini')
        if not self.initialized:        
            if not os.path.exists(os.path.dirname(fname)):
                os.makedirs(os.path.dirname(fname))
            self.fp = file(fname, 'a')
            self.initialized = True        

    def __del__(self):
        self.fp.close()

    def _get_objects(self, portal_type):
        for brain in plone.portal_catalog(portal_type=portal_type):
            obj = self.plone.unrestrictedTraverse(brain.getPath())
            obj_path = brain.getPath()
            folder_path = obj_path.replace(self.portal_path, '')[1:]
            yield obj, obj_path, folder_path

    def write_common(self, obj, folder_path):

        def fix_oneline(s):
            s = s.replace('\r\n', ' ')
            s = s.replace('\n', ' ')
            return s

        from Products.CMFCore.WorkflowCore import WorkflowException

        wf_tool = obj.portal_workflow
        try:
            review_state = wf_tool.getInfoFor(obj, 'review_state')
        except WorkflowException:

            review_state = ''

        description = obj.Description()

        print >>self.fp, '[%s-%s]' % (self.ident, obj.absolute_url(1))
        print >>self.fp, 'path = %s' % folder_path.lstrip('/')
        print >>self.fp, 'id = %s' % obj.getId()
        print >>self.fp, 'title = %s' % fix_oneline(obj.Title())
        print >>self.fp, 'Description = %s' % fix_oneline(description)
        print >>self.fp, 'owner = %s' % obj.getOwner()
        print >>self.fp, 'review-state = %s' % review_state
        print >>self.fp, 'created = %f' % obj.created().timeTime()
        print >>self.fp, 'effective = %f' % obj.effective().timeTime()
        print >>self.fp, 'expires = %f' % obj.expires().timeTime()
        print >>self.fp, 'subjects = %s' % ','.join(obj.Subject())

        text_format = None
        if hasattr(obj, 'text_format'):
            text_format = obj.text_format
            self.write('text-format', text_format)

        # content-type:
        ct = None
        try:
            ct = obj.getContentType()
        except AttributeError:
            ct = obj.content_type()
        if ct is not None: 
            if text_format in ('html', 'structured-text'):
                ct = 'text/html'
            self.write('content-type', ct)


        # raw data
        schema = obj.Schema()
        for field in schema.fields():
            field_class = field.__class__.__name__
            if 'ImageField' in field_class or 'FileField' in field_class:
                continue
            accessor = field.accessor
            try:
                value = getattr(obj, accessor)()
            except:
                continue
#            print >>self.fp, 'raw_%s = %s' % (field.getName(), value)


    def write_leadout(self):
        print >>self.fp

    def write_binary(self, data, suffix='', key='filename'):
            dirpath = os.path.join(self.export_dir, self.ident)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            tempf = tempfile.mktemp(dir=dirpath) + suffix
            open(tempf, 'wb').write(str(data))
            self.write(key, os.path.abspath(tempf))


    def write(self, key, value):
        print >>self.fp, '%s = %s' % (key, value)

    def export(self, portal_type):

        print 'Exporting %s' % portal_type

        for obj, obj_path, folder_path in self._get_objects(portal_type):
            if self.verbose:
                print '-> %s' % obj_path

            if getattr(self, 'folderish', False):
                self.write_common(obj, '/'.join(folder_path.split('/')[:-1]))
            else:
                self.write_common(obj, folder_path)
            if hasattr(self, 'export2'):
                self.export2(obj)
            self.write_leadout()

class DocumentHandler(BaseHandler):

    portal_types = ('Document',)
    ident = 'documents'

    def export2(self, obj):
        try:
            data = obj.getText()
        except:
            try:
                data = obj.text
            except:
                data = obj.getRawText()

        self.write_binary(data)

registerHandler(DocumentHandler)

class FolderHandler(BaseHandler):
    portal_types = ('ATFolder', 'Folder', 'Photo Album')
    ident = 'folder'
    folderish = True

registerHandler(FolderHandler)


class NewsHandler(BaseHandler):
    portal_types = ('ATNewsItem', 'NewsItem', 'News Item')
    ident = 'newsitem'

    def export2(self, obj):
        try:
            self.write_binary(obj.getText())
        except:
            self.write_binary(obj.getRawText())

registerHandler(NewsHandler)


class LinkHandler(BaseHandler):
    portal_types = ('Link', 'ATLink')
    ident = 'link'

    def export2(self, obj):
        self.write('url ', obj.getRemoteUrl())

registerHandler(LinkHandler)


class ImageHandler(BaseHandler):
    portal_types = ('Image', 'ATImage','Photo')
    ident = 'image'

    def export2(self, obj):
        self.write_binary(str(obj.data))

registerHandler(ImageHandler)

class ZWikiPageHandler(BaseHandler):
    portal_types = ('Wiki Page',)
    ident = 'zwikipage'

    def export2(self, obj):
        pickledata = obj.manage_exportObject(download=True)
        self.write_binary(pickledata, 'zexp')

registerHandler(ZWikiPageHandler)

class CMFBibliographyHandler(BaseHandler):
    portal_types = 'BibliographyFolder'
    ident = 'cmbibliography'

    def export2(self, obj):
        pickledata = obj.manage_exportObject(download=True)
        self.write_binary(pickledata, 'zexp')

registerHandler(CMFBibliographyHandler)


class FileHandler(ImageHandler):
    portal_types = ('File', 'ATFile')
    ident = 'files'

registerHandler(FileHandler)

class AnbieterHandler(BaseHandler):
    portal_types = ('Anbieter', )
    ident = 'anbieter'

    def export2(self, obj):
        schema = obj.Schema()

        self.write('path', 'anbieter/%s' % obj.getId())

        logo = obj.getLogo()
        if logo:
            self.write_binary(str(logo.data), key='filename-logo')
        for name in ('firmenname',
                    'ansprechpartner_anrede',
                    'ansprechpartner_vorname',
                    'ansprechpartner_nachname',
                    'ansprechpartner',
                    'strasse',
                    'plz',
                    'ort',
                    'plz_bereich',
                    'country',
                    'telefon',
                    'fax',
                    'email',
                    'leistungsbeschreibung',
                    'url_homepage',
                    'course_provider',
                    'courses_url',
                    'dzug_vereins_mitglied',):

            field = schema[name]
            accessor = field.accessor
            print accessor, field
            value = getattr(obj, accessor)()
            self.write(name, str(value))


registerHandler(AnbieterHandler)

class JobGesuchHandler(BaseHandler):
    portal_types = ('JobGesuch',)
    ident = 'jobgesuch'

    def export2(self, obj):
        try:
            self.write_binary(obj.getBeschreibung(), key='filename-beschreibung')
            self.write_binary(obj.getKontakt(), key='filename-kontakt')
        except:
            pass

registerHandler(JobGesuchHandler)

class JobAngebotHandler(BaseHandler):
    portal_types = ('JobAngebot',)
    ident = 'jobangebot'

    def export2(self, obj):
        try:
            self.write_binary(obj.getBeschreibung(), key='filename-beschreibung')
            self.write_binary(obj.getKontakt(), key='filename-kontakt')
            self.write('ort', obj.getOrt())
            self.write('befristet', obj.getBefristet())
        except:
            pass

registerHandler(JobAngebotHandler)


if __name__ == '__main__':

    from optparse import OptionParser
    from AccessControl.SecurityManagement import newSecurityManager
    import Zope

    parser = OptionParser()
    parser.add_option('-u', '--user', dest='username', default='admin')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      default=False)

    options, args = parser.parse_args()

    for path in args:

        plone = app.restrictedTraverse(path)
        group = ''           
        export_dir = 'export-%s' % plone.getId()
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir, ignore_errors=True)
        os.makedirs(export_dir)

        print '-'*80    
        print 'Exporting Plone site: %s' % path
        print 'Export directory:  %s' % os.path.abspath(export_dir)
        print '-'*80    

        app = Zope.app()
        uf = app.acl_users
        user = uf.getUser(options.username)
        if user is None:
            raise ValueError('Unknown user: %s' % options.username)
        newSecurityManager(None, user.__of__(uf))

        export_members(plone, export_dir, options.verbose)
        for portal_type in handlers:
            handler = handlers[portal_type]
            exporter = handler(plone, export_dir, options.verbose)
            exporter.export(portal_type)
