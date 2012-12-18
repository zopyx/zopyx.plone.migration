zopyx.plone.migration
=====================

Export/import migration script for Plone 2/3 sites to Plone 4

The purpose of this package is to provide scripts to export AT-based content
into a more generic format that can be used by an importer script for
re-import into a Plone 4 site.

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
To be written


Licence
-------
This package is licenced under the Zope Public Licence V 2.1 (ZPL 2.1)

Author
------

ZOPYX Limited
Andreas Jung
Hundskapfklinge 33
D-72074 Tübingen, Germany
www.zopyx.com
info@zopyx.com

