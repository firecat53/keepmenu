Keepmenu
========

Select entries from Keepass databases using dmenu or Rofi_ and type username
and/or password into the active window.

Inspired in part by Passhole_, but I wanted something more dmenu and less
command line focused.

I'm very aware of pass and passmenu, but I've found that the Keepass options for
other platforms are much easier to use, especially for the non-technically
oriented. Thus...synchronized passwords and everyone is happy!

Features
--------

- Prompts for and saves initial database and keyfile locations if config file
  isn't setup before first run.
- Set multiple databases in the config file, including key files.
- Auto-type username and/or password on selection. No clipboard copy/paste
  involved.
- Alternatively, select any single field and have it type into the active
  window. Notes fields can be viewed line-by-line from within dmenu and the
  selected line will be typed.
- Enter database passphrase and optionally gpg encrypt and cache it using an
  existing gpg-agent key.
- Set cache expiration time for saving the database passphrase
- Optional Pinentry support for secure passphrase entry.
- Possible future features:
  + Add/edit/delete entries
  + View/copy password notes

License
-------

- MIT

Requirements
------------

1. Python 2.7+ or 3.2+
2. Pykeepass_, PyUserInput_, and pygpgme_. Install via pip or your
   distribution's package manager, if available.
3. Dmenu. Basic support is included for Rofi_, but most Rofi
   configuration/theming should be done via Xresources.
4. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.

Installation
------------

- Installation

  + In a virtualenv with pip. Link to the executable in
    <path/to/virtualenv/bin/keepmenu> ::

        mkvirtualenv keepmenu
        pip install keepmenu

  + From git. Just clone, install requirements and run
  + Available in `Archlinux AUR`_. 

- If you start keepmenu for the first time without a config file, it will prompt
  you for database and keyfile locations and save them.

- Copy config.ini.example to ~/.config/keepmenu/config.ini, or use it as a
  reference for additional options.

  + Add your database(s) and keyfile(s)
  + Add `gpg_key` if you want the database passphrase cached
  + Set the dmenu_command to `rofi` if you are using that instead

- If using Rofi, you can try some of the command line options in config.ini or
  set them using the `dmenu_command` setting, but I haven't tested most of them
  so I'd suggest configuring via .Xresources where possible. 
- If using dmenu for passphrase entry (pinentry not set), dmenu options in the
  [dmenu_passphrase] section of config.ini will override those in [dmenu] so you
  can, for example, set the normal foreground and background colors to be the
  same to obscure the passphrase.

.. warning:: If you choose to store your database password into config.ini, make
   sure to `chmod 600 config.ini`. This is not secure and I only added it as a
   convenience for testing.

Usage
-----

- Run script or bind to keystroke combination
- Hit Enter immediately after dmenu opens ("`View/Type individual entries`") to
  switch modes to view and/or type the individual fields for the entry.

.. _Rofi: https://davedavenport.github.io/rofi/
.. _Passhole: https://github.com/purduelug/passhole
.. _Pykeepass: https://github.com/pschmitt/pykeepass
.. _PyUserInput: https://github.com/PyUserInput/PyUserInput
.. _pygpgme: https://pypi.python.org/pypi/pygpgme
.. _Archlinux AUR: https://aur.archlinux.org/packages/python-keepmenu-git
