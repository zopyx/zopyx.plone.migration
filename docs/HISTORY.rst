Changes
=======

0.2.9-dev (unreleased)
----------------------

- Avoid memory leaks by adding the posibility of batching content exports.
  [thet]

- Fix setLayout and reference field importing.
  [jensens]

- Handle LinguaPlone translations. Note, in cases where Folders and Documents
  are mixed within a Folder, the correct order isn't preserved.
  [jensens]

- Deal with exporting Plone 2.1 GRUF groups.
  [jensens]

- Various fixes for export while using with python 2.4 and Plone 2.5.
  [ichim-david]

- Fix edge case where obj.objectValues() recursed infinitely (SimpleAlias).
  [petschki]

- Generalize ReferenceField behaviour to use 'getRaw' method.
  [petschki]

- Add support for multiple file/image fields in schema.
  [petschki]

- Add support for Topic Criterions export/import.
  [petschki]

- Add "-i/--ignore" (comma separated ignore types) to exporter console script.
  [petschki]


0.2.8 (08.07.2013)
------------------

- PloneGazette related fixes and workarounds.


0.2.0 (14.01.2013)
------------------

- Various fixes.


0.1.0 (18.12.2012)
------------------

- Initial release.
