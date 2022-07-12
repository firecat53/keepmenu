#!/usr/bin/env python3  # pylint: disable=missing-docstring

from setuptools import setup

setup(name="keepmenu",
      version="1.3.1",
      description="Dmenu frontend for Keepass databases",
      long_description=open('README.md', 'rb').read().decode('utf-8'),
      long_description_content_type="text/markdown",
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/keepmenu",
      download_url="https://github.com/firecat53/keepmenu/tarball/1.3.1",
      packages=['keepmenu'],
      entry_points={
          'console_scripts': ['keepmenu=keepmenu.__main__:main']
      },
      data_files=[('share/doc/keepmenu', ['README.md', 'LICENSE',
                                          'config.ini.example']),
                  ('share/doc/keepmenu/docs', ['docs/install.md',
                                               'docs/configure.md',
                                               'docs/usage.md']),
                  ('share/man/man1', ['keepmenu.1'])],
      install_requires=["pynput", "pykeepass>=4.0.0"],
      license="GPL3",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Topic :: Utilities',
      ],
      keywords=("dmenu keepass keepassxc"),
      )
