Keepmenu
========

Read and copy entries from Keepass databases using dmenu or Rofi_.

Features
--------

- Set multiple databases in the config file, including key files.
- Auto-type username and/or password on selection.
- Enter database password and optionally(TODO) store it in a running gpg-agent instance.
- Optional Pinentry support for secure passphrase entry

License
-------

- MIT

Requirements
------------

1. Python 2.7+ or 3.2+
2. Pykeepass_ and PyUserInput_. Install via pip or your distribution's package manager, if available.
3. Dmenu. Basic support is included for Rofi_, but most Rofi configuration/theming should be done via Xresources.
4. (optional) Pinentry. Make sure to set which flavor of pinentry command to use in the config file.

Installation
------------

- Set your dmenu_command in config.ini if it's not 'dmenu' (for example dmenu_run or rofi). The alternate command should still respect the -l, -p and -i flags.
- Copy config.ini.example to ~/.config/keepmenu/config.ini and edit.
- If using Rofi, you can try some of the command line options in config.ini or set them using the `dmenu_command` setting, but I haven't tested most of them so I'd suggest configuring via .Xresources where possible. 
- Copy script somewhere in $PATH
- If desired, copy the keepmenu.desktop to /usr/share/applications or ~/.local/share/applications.
- If using dmenu for passphrase entry (pinentry not set), dmenu options in the [dmenu_passphrase] section of config.ini will override those in [dmenu] so you can, for example, set the normal foreground and background colors to be the same to obscure the passphrase.

Usage
-----

- Run script or bind to keystroke combination

.. _Rofi: https://davedavenport.github.io/rofi/
.. _Pykeepass: https://github.com/pschmitt/pykeepass
.. _PyUserInput: https://github.com/PyUserInput/PyUserInput
