Keepmenu
========

Read and copy entries from Keepass databases using dmenu or Rofi_.

Features
--------

- Set multiple databases in the config file, including key files
- Enter database password and optionally store it in a running gpg-agent instance.
- Optional Pinentry support for secure passphrase entry
- Copy using xclip or xsel

License
-------

- MIT

Requirements
------------

1. Python 2.7+ or 3.2+
2. Pykeepass_
3. Dmenu. Basic support is included for Rofi_, but most Rofi configuration/theming should be done via Xresources.
7. (optional) Pinentry. Make sure to set which flavor of pinentry command to use in the config file.

Installation
------------

- Set your dmenu_command in config.ini if it's not 'dmenu' (for example dmenu_run or rofi). The alternate command should still respect the -l, -p and -i flags.
- To customize dmenu appearance, copy config.ini.example to ~/.config/keepmenu/config.ini and edit.
- Set default terminal (xterm, urxvtc, etc.) command in config.ini if desired.
- If using Rofi, you can try some of the command line options in config.ini or set them using the `dmenu_command` setting, but I haven't tested most of them so I'd suggest configuring via .Xresources where possible. 
- Copy script somewhere in $PATH
- If desired, copy the keepmenu.desktop to /usr/share/applications or ~/.local/share/applications.
- If using dmenu for passphrase entry (pinentry not set), dmenu options in the [dmenu_passphrase] section of config.ini will override those in [dmenu] so you can, for example, set the normal foreground and background colors to be the same to obscure the passphrase.

Usage
-----

- Run script or bind to keystroke combination
- If desired, dmenu or Rofi options can be passed on the command line instead of
  or in addition to the config file. These will override options in the config
  file.

.. _Rofi: https://davedavenport.github.io/rofi/
.. _Pykeepass: https://github.com/pschmitt/pykeepass
