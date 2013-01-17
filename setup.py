from setuptools import setup, find_packages
import os

version = '0.2.3'

setup(name='zopyx.plone.migration',
      version=version,
      description="Export/import scripts for migration Plone 2+3 to Plone 4",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        ],
      keywords='Zope Plone Migration',
      author='Andreas Jung',
      author_email='info@zopyx.com',
      url='http://pypi.python.org/pypi/zopyx.plone.migration',
      license='ZPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['zopyx', 'zopyx.plone'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'lxml',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      [console_scripts]
      exporter = zopyx.plone.migration.exporter:main
      importer = zopyx.plone.migration.importer:main
      """,
      setup_requires=[],
      paster_plugins=[],
      )
