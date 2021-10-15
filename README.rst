Keepmenu
========

.. Warning:: Keepmenu now depends on pykeepass>=4.0.0. It will break if you are
   using a current distribution-packaged pykeepass. The easiest way to update
   pykeepass is:

            pip install --user -U pykeepass

Fully featured Dmenu/Rofi frontend for managing Keepass databases.

Inspired in part by Passhole_, but I wanted something more dmenu and less
command line focused.

I'm very aware of pass and passmenu, but I've found that the Keepass options for
other platforms are much easier to use, especially for the non-technically
oriented. Thus...synchronized passwords and everyone is happy!

Features
--------

- *NOTE* Only support .kdbx databases, not .kdb
- Auto-type username and/or password on selection. No clipboard copy/paste
  involved.
- Use a custom Keepass 2.x style auto-type sequence if you have one defined
  (except for character repetition and the 'special commands'). Set it per entry
  or set a default in the config file for all entries. Disable autotype for an
  entry, if desired.
- Select any single field and have it typed into the active window. Notes fields
  can be viewed line-by-line from within dmenu and the selected line will be
  typed when selected.
- Open the URL in the default web browser from the View/Type menu.
- Alternate keyboard languages and layouts supported via xdotool or ydotool (for
  Wayland)
- Edit entry title, username, URL and password (manually typed or auto-generate)
- Edit notes using terminal or gui editor (set in config.ini, or uses $EDITOR)
- Add and Delete entries
- Rename, move, delete and add groups
- Prompts for and saves initial database and keyfile locations if config file
  isn't setup before first run.
- Set multiple databases and keyfiles in the config file. Switch databases on
  the fly.
- Hide selected groups from the default and 'View/Type Individual entries' views.
- Keepmenu runs in the background after initial startup and will retain the
  entered passphrase for `pw_cache_period_min` minutes after the last activity.
- Configure the characters and groups of characters used during password
  generation in the config file (see config.ini.example for instructions).
  Multiple character sets can be selected on the fly when using Rofi if the
  `-multi-select` option is passed via `dmenu_command`.
- Optional Pinentry support for secure passphrase entry.
- `Keepass field references`_ are supported.
- Supports displaying of expiring/expired passwords and shows the expiry time where set
- Add, edit and type TOTP codes. RFC 6238, Steam and custom settings are supported.

License
-------

- GPLv3

Requirements
------------

1. Python 3.6+.
2. Pykeepass_ >= 4.0.0 and pynput_. Install via pip or your distribution's package
   manager, if available.
3. Dmenu or Rofi. Rofi configuration/theming should be done via Rofi themes.
4. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.
5. (optional) xdotool or ydotool (for Wayland). If you have a lot of Unicode
   characters or use a non-U.S.  English keyboard layout, xdotool is necessary
   to handle typing those characters.

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
  + To use a command (e.g. gpg) to lookup db password, set `password_cmd_<n>`
    in config.ini.
  + Adjust `pw_cache_period_min` if desired. Default is 6 hours (360 min).
  + Set the dmenu_command to `rofi` if you are using that instead
  + Adjust the autotype_default, if desired. Allowed codes are the
    `Keepass 2.x codes`_ except for repetitions and most command codes. `{DELAY
    x}` (in milliseconds) is supported.
    Individual autotype sequences can be edited or disabled inside Keepmenu.
  + Set `type_library = xdotool` or `type_library = ydotool` (Wayland) if you
    need support for non-U.S. English keyboard layouts and/or characters.

    * When using xdotool, call `setxkbmap` to set your keyboard type somewhere
      in your window manager or desktop environment initialization. For example:
      `exec setxkbmap de` in ~/.config/i3/config.

- If using Rofi, pass desired theme via `dmenu_command = rofi -theme
  <theme>.rasi`. Dmenu options are also passed via `dmenu_command`
- New sets of characters can be set in config.ini in the `[password_chars]`
  section. A new preset for each custom set will be listed in addition to the
  default presets. If you redefine one of the default sets (upper, lower,
  digits, punctuation), it will replace the default values.
- New preset groups of character sets can be defined in config.ini in the
  `[password_char_presets]` section. You can set any combination of default and
  custom character sets. A minimum of one character from each distinct set will
  be used when generating a new password. If any custom presets are defined, the
  default presets will not be displayed unless they are uncommented.

.. Warning:: If you choose to store your database password into config.ini, make
   sure to `chmod 600 config.ini`. This is not secure and I only added it as a
   convenience for testing.

Usage
-----

- Run script or bind to keystroke combination
- Enter database and keyfile if not entered into config.ini already.
- Start typing to match entries.
- Hit Enter immediately after dmenu opens ("`View/Type individual entries`") to
  switch modes to view and/or type the individual fields for the entry. If
  selected, the URL will open in the default browser instead of being typed.
- To view a password without typing it, use the 'Edit Entries' option, then
  select the entry, select 'Password' then select 'Manually enter password'.
  Type 'ESC' to exit without making changes.

Options
-------
usage: keepmenu [-h] [-a AUTOTYPE] [-d DATABASE] [-k KEY_FILE]

--help, -h Output a usage message and exit.

-a AUTOTYPE, --autotype AUTOTYPE Override autotype sequence in config.ini

-d DATABASE, --database DATABASE File path to a database to open, skipping the database selection menu

-k KEYFILE, --keyfile KEY_FILE File path of the keyfile needed to open the database specified by --database/-d

Tests
-----

- To run tests: `python tests/tests.py`

.. _Rofi: https://davedavenport.github.io/rofi/
.. _Passhole: https://github.com/purduelug/passhole
.. _Keepass field references: https://keepass.info/help/base/fieldrefs.html
.. _Pykeepass: https://github.com/pschmitt/pykeepass
.. _pynput: https://github.com/moses-palmer/pynput
.. _Archlinux AUR: https://aur.archlinux.org/packages/python-keepmenu-git
.. _Keepass 2.x codes: https://keepass.info/help/base/autotype.html#autoseq
