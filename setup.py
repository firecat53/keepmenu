#!/usr/bin/env python  # pylint: disable=missing-docstring

from setuptools import setup

setup(name="keepmenu",
      version="0.5.2",
      description="Dmenu frontend for Keepass databases",
      long_description=open('README.rst', 'rb').read().decode('utf-8'),
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/keepmenu",
      download_url="https://github.com/firecat53/keepmenu/tarball/0.5.2",
      scripts=['keepmenu'],
      data_files=[('share/doc/keepmenu', ['README.rst', 'LICENSE.txt',
                                          'config.ini.example'])],
      install_requires=["PyUserInput", "pykeepass"],
      license="MIT",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Topic :: Utilities',
      ],
      keywords=("dmenu keepass keepassxc"),
     )
