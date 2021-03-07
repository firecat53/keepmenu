#!/usr/bin/env python3  # pylint: disable=missing-docstring

from setuptools import setup

setup(name="keepmenu",
      version="0.6.5",
      description="Dmenu frontend for Keepass databases",
      long_description=open('README.rst', 'rb').read().decode('utf-8'),
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/keepmenu",
      download_url="https://github.com/firecat53/keepmenu/tarball/0.6.5",
      scripts=['keepmenu'],
      data_files=[('share/doc/keepmenu', ['README.rst', 'LICENSE',
                                          'config.ini.example']),
                  ('share/man/man1', ['keepmenu.1'])],
      install_requires=["pynput", "pykeepass"],
      license="GPL3",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Topic :: Utilities',
      ],
      keywords=("dmenu keepass keepassxc"),
     )
