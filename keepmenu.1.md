---
title: Keepmenu
section: 1
header: User Manual
footer: Keepmenu 1.1.0
date: 18 October 2021
---

# NAME

keepmenu - Fully featured Dmenu/Rofi frontend for autotype and managing of Keepass databases.

# SYNOPSIS

**keepmenu** [**--database** file] [**--keyfile** file] [**--autotype** pattern]

# DESCRIPTION

**Keepmenu** is a fast and minimal application to facilitate password entry and
manage most aspects of Keepass .kdbx databases.  It is inspired in part by
Passhole, but is more dmenu and less command line focused.

# OPTIONS

**-d**, **--database** Path to Keepass database

**-k**, **--keyfile**  Path to keyfile

**-a**, **--autotype**  Autotype sequence from https://keepass.info/help/base/autotype.html#autoseq . Overrides global default from config.ini for current database.

# EXAMPLES

	keepmenu
    keepmenu -d ~/docs/totp_passwords.kdbx -a '{TOTP}{ENTER}'

# CONFIGURATION  

If you start keepmenu for the first time without a config file, it will prompt
you for database and keyfile locations and save them in a default config file.

OR Copy config.ini.example to ~/.config/keepmenu/config.ini and use it as a
reference for additional options.

## config.ini options and defaults

| Section                   | Key                          | Default                                                |
|---------------------------|------------------------------|--------------------------------------------------------|
| `[dmenu]`                 | `dmenu_command`              | `dmenu`                                                |
|                           | `pinentry`                   | None                                                   |
| `[dmenu_passphrase]`      | `obscure`                    | `False`                                                |
|                           | `obscure_color`              | `#222222`                                              |
| `[database]`              | `database_n`                 | None                                                   |
|                           | `keyfile_n`                  | None                                                   |
|                           | `password_n`                 | None                                                   |
|                           | `password_cmd_n`             | None                                                   |
|                           | `autotype_default_n`         | None                                                   |
|                           | `pw_cache_period_min`        | `360`                                                  |
|                           | `editor`                     | `vim`                                                  |
|                           | `terminal`                   | `xterm`                                                |
|                           | `gui_editor`                 | None                                                   |
|                           | `type_library`               | `pynput`                                               |
|                           | `hide_groups`                | None                                                   |
|                           | `autotype_default`           | `{USERNAME}{TAB}{PASSWORD}{ENTER}`                     |
| `[password_chars]`        | `lower`                      | `abcdefghijklmnopqrstuvwxyz`                           |
|                           | `upper`                      | `ABCDEFGHIJKLMNOPQRSTUVWXYZ`                           |
|                           | `digits`                     | `0123456789`                                           |
|                           | `punctuation`                | ``!"#$%%&'()*+,-./:;<=>?@[\]^_`{│}~``                  |
|                           | `Custom Name(s)`             | `Any string`                                           |
| `[password_char_presets]` | `Letters+Digits+Punctuation` | `upper lower digits punctuation`                       |
|                           | `Letters+Digits`             | `upper lower digits`                                   |
|                           | `Letters`                    | `upper lower`                                          |
|                           | `Digits`                     | `digits`                                               |
|                           | `Custom Name(s)`             | `Any combo of [password_chars] entries`                |

# FILES

~/.config/keepmenu/config.ini

# AUTHOR

Scott Hansen - <firecat4153@gmail.com>

# COPYRIGHT  

GNU General Public License 3

# SEE ALSO

Full documentation available at https://github.com/firecat53/keepmenu
