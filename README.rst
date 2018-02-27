Keepmenu
========

Fully featured Dmenu/Rofi frontend for managing Keepass databases.

Inspired in part by Passhole_, but I wanted something more dmenu and less
command line focused.

I'm very aware of pass and passmenu, but I've found that the Keepass options for
other platforms are much easier to use, especially for the non-technically
oriented. Thus...synchronized passwords and everyone is happy!

Features
--------

- Auto-type username and/or password on selection. No clipboard copy/paste
  involved.
- Select any single field and have it typed into the active window. Notes fields
  can be viewed line-by-line from within dmenu and the selected line will be
  typed when selected.
- Alternate keyboard languages and layouts supported via xdotool.
- Edit entry title, username, URL and password (manually typed or auto-generate)
- Edit notes using terminal or gui editor (set in config.ini, or uses $EDITOR)
- Add and Delete entries
- Rename, move, delete and add groups
- Prompts for and saves initial database and keyfile locations if config file
  isn't setup before first run.
- Set multiple databases and keyfiles in the config file.
- Hide selected groups from the default and 'View/Type Individual entries' views.
- Keepmenu runs in the background after initial startup and will retain the
  entered passphrase for `pw_cache_period_min` minutes.
- Optional Pinentry support for secure passphrase entry.

License
-------

- MIT

Requirements
------------

1. Python 2.7+ or 3.2+
2. Pykeepass_ and PyUserInput_. Install via pip or your distribution's package
   manager, if available.
3. Dmenu. Basic support is included for Rofi_, but most Rofi
   configuration/theming should be done via Xresources.
4. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.
5. (optional) xdotool. If you have a lot of Unicode characters or use a non-U.S.
   English keyboard layout, xdotool is necessary to handle typing those
   characters.

Installation
------------

- Installation

  + `pip install --user keepmenu`. Add ~/.local/bin to $PATH
  + In a virtualenv with pip. Link to the executable in
    <path/to/virtualenv/bin/keepmenu> ::

        mkvirtualenv keepmenu
        pip install keepmenu

  + From git. Just clone, install requirements and run
  + Available in `Archlinux AUR`_. 

- If you start keepmenu for the first time without a config file, it will prompt
  you for database and keyfile locations and save them in a default config file.

- Copy config.ini.example to ~/.config/keepmenu/config.ini, or use it as a
  reference for additional options.

  + Add your database(s) and keyfile(s)
  + Adjust `pw_cache_period_hrs` if desired. Default is 6 hours.
  + Set the dmenu_command to `rofi` if you are using that instead
  + Set `type_library = xdotool` if you need support for non-U.S. English
    keyboard layouts and/or characters.

    * When using xdotool, call `setxkbmap` to set your keyboard type somewhere
      in your window manager or desktop environment initialization. For example:
      `exec setxkbmap de` in ~/.config/i3/config. 

- If using Rofi, you can try some of the command line options in config.ini or
  set them using the `dmenu_command` setting, but I haven't tested most of them
  so I'd suggest configuring via .Xresources where possible. 
- If using dmenu for passphrase entry (pinentry not set), dmenu options in the
  [dmenu_passphrase] section of config.ini will override those in [dmenu] so you
  can, for example, set the normal foreground and background colors to be the
  same to obscure the passphrase.

.. Warning:: If you choose to store your database password into config.ini, make
   sure to `chmod 600 config.ini`. This is not secure and I only added it as a
   convenience for testing.

Usage
-----

- Run script or bind to keystroke combination
- Enter database and keyfile if not entered into config.ini already.
- Start typing to match entries.
- Hit Enter immediately after dmenu opens ("`View/Type individual entries`") to
  switch modes to view and/or type the individual fields for the entry.

.. _Rofi: https://davedavenport.github.io/rofi/
.. _Passhole: https://github.com/purduelug/passhole
.. _Pykeepass: https://github.com/pschmitt/pykeepass
.. _PyUserInput: https://github.com/PyUserInput/PyUserInput
.. _Archlinux AUR: https://aur.archlinux.org/packages/python-keepmenu-git
