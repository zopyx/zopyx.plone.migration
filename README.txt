zopyx.plone.migration
=====================

Export/import migration script for Plone 2/3 sites to Plone 4

The purpose of this package is to provide scripts to export AT-based content
into a more generic format that can be used by an importer script for
re-import into a Plone 4 site. The main goal of the scripts is to get
Plone content in a more clean way out of Plone 2/3 site and to import it
into a clean way into a fresh Plone 4 site.


Installation
------------

Add the following to your buildout::

    [buildout]
    parts = 
        exportimport


    [exportimport]
    recipe = zc.recipe.egg:scripts
    eggs = zopyx.plone.migration


Export of a Plone site
----------------------

Prequisites: your Plone site/server must be stopped or you must
be running Plone through ZEO.

The exporter will export the following items from a Plone site:

- members (member name, member password, global member roles)
- groups (group name, group members, global group roles)
- structure of the site (folder structure including local roles
   and review state)
- all Archetypes-based content with all metadata of a content item
   that has been defined through an Archetype schema (plus
   some extra data like review state, local roles, related items)
- workflow states (also deals with PlaceFulworkflow)
- local roles (including blocking/inheritance of local roles)
- object position in parent
- related items
- default pages


Usage::

    bin/instance run bin/exporter.py --path /path/to/<plone_id> --output <directory>

The exporter will create a self-contained directory with the exported data
unter ``<directory>/<plone_id>``. The directory contains two INI files
``contents.ini`` and ``structure.ini``  that describe the hierarchy structure
of the exported site and exported contents.

The metadata and real content of each object is stored within the ``content``
subfolder. This directory will contain on file per exported content object.
The filename is determined by the original UID of the content object. For
binary files like File or Image there is a <uid>.bin file which will contain
the original binary data.  The files  (except the ``.bin`` files) are
serialized using Python's Pickle mechanism in order to avoid serialization
issues and to preserve the data as is.

In addition the exporter cares out the export of members and groups
(members.ini, groups.ini)

Note that the ``bin/exporter`` script is **not directly** callable.
It must always be run using the ``bin/instance run somescript.py`` mechanism
of the Plone startup script - always!

The export has been tested against Plone 2.5 and Plone 3.3.

Importing to a new Plone site
-----------------------------

For importing a formerly exported Plone site you must use the following
command-line:


    bin/instance run bin/importer -i <input-directory> [-t] [-v]

``input-directory`` is here the full path to the formerly created output
directory (``--output`` parameter + site prefix). The import script will
create a new Plone site under ``sites/<site-prefix>``. The ``site-prefix`` is
taken from the last path component of the output directory. You can specify
the ``-t`` or ``--timestamp`` option in order to add a timestamp to the site
id of the new Plone site. This is useful for re-running the importer script
multiple times. The ``sites`` prefix (a folder in Plone can be customized
using the ``-d`` or ``--dest-folder`` commandline option. The importer assumes
that there is an ``admin`` account with manager permissions inside the root
acl_users folder (use ``-u`` or ``-user`` option for overriding the default
admin account name).

To do
-----

- support commandline parameter for specifying a list of extension profiles
  to be used while creating a new Plone site
- better dealing with arbitrary --dest-folder options

Licence
-------
This package is licenced under the Zope Public Licence V 2.1 (ZPL 2.1)

Author
------

| ZOPYX Limited
| Andreas Jung
| Hundskapfklinge 33
| D-72074 Tübingen, Germany
| www.zopyx.com
| info@zopyx.com

Written for Veit Schiele Communications GmbH (www.veit-schiele.de)
