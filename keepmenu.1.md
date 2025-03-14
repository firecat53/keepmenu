---
title: Keepmenu
section: 1
header: User Manual
footer: Keepmenu 1.4.2
date: 05 July 2024
---

# NAME

keepmenu - Fully featured Dmenu/Rofi frontend for autotype and managing of Keepass databases.

# SYNOPSIS

**keepmenu** [**--autotype** pattern] [**--config** file] [**--clipboard**] [**--database** file] [**--keyfile** file] [**--no-prompt**] [**--totp**]

# DESCRIPTION

**Keepmenu** is a fast and minimal application to facilitate password entry and
manage most aspects of Keepass .kdbx databases.  It is inspired in part by
Passhole, but is more dmenu and less command line focused.

# OPTIONS

**-a**, **--autotype**  Autotype sequence from https://keepass.info/help/base/autotype.html#autoseq . Overrides global default from config.ini for current database.

**-c**, **--config**   Path to config file

**-C**, **--clipboard** Select to clipboard

**-d**, **--database** Path to Keepass database

**-k**, **--keyfile**  Path to keyfile

**-n**, **--no-prompt**  Do not prompt for database password

**-s**, **--show** Search term(s)

**-t**, **--totp**  TOTP mode

# EXAMPLES

    keepmenu
    keepmenu -t
    keepmenu -c /etc/keepmenu/config.ini
    keepmenu -d ~/docs/totp_passwords.kdbx -a '{TOTP}{ENTER}'
    keepmenu -d ~/passwords.kdbx -k ~/passwords.keyfile -a '{S:security question}{ENTER}'
    keepmenu -s "production/ssh db" -d ~/passwords.kdbx

# CONFIGURATION

If you start keepmenu for the first time without a config file, it will prompt
you for database and keyfile locations and save them in a default config file.

OR Copy config.ini.example to ~/.config/keepmenu/config.ini and use it as a
reference for additional options.

Alternatively you can specify the file path to your config.ini using the -c/--config flag.

## config.ini options and defaults

| Section                   | Key                          | Default                                 |
|---------------------------|------------------------------|-----------------------------------------|
| `[dmenu]`                 | `dmenu_command`              | `dmenu`                                 |
|                           | `pinentry`                   | None                                    |
|                           | `title_path`                 | `True`                                  |
| `[dmenu_passphrase]`      | `obscure`                    | `False`                                 |
|                           | `obscure_color`              | `#222222`                               |
| `[database]`              | `database_n`                 | None                                    |
|                           | `keyfile_n`                  | None                                    |
|                           | `password_n`                 | None                                    |
|                           | `password_cmd_n`             | None                                    |
|                           | `autotype_default_n`         | None                                    |
|                           | `pw_cache_period_min`        | `360`                                   |
|                           | `editor`                     | `vim`                                   |
|                           | `terminal`                   | `xterm`                                 |
|                           | `gui_editor`                 | None                                    |
|                           | `type_library`               | `pynput`                                |
|                           | `hide_groups`                | None                                    |
|                           | `autotype_default`           | `{USERNAME}{TAB}{PASSWORD}{ENTER}`      |
|                           | `type_url`                   | `False`                                 |
| `[password_chars]`        | `lower`                      | `abcdefghijklmnopqrstuvwxyz`            |
|                           | `upper`                      | `ABCDEFGHIJKLMNOPQRSTUVWXYZ`            |
|                           | `digits`                     | `0123456789`                            |
|                           | `punctuation`                | ``!"#$%%&'()*+,-./:;<=>?@[\]^_`{│}~``   |
|                           | `Custom Name(s)`             | `Any string`                            |
| `[password_char_presets]` | `Letters+Digits+Punctuation` | `upper lower digits punctuation`        |
|                           | `Letters+Digits`             | `upper lower digits`                    |
|                           | `Letters`                    | `upper lower`                           |
|                           | `Digits`                     | `digits`                                |
|                           | `Custom Name(s)`             | `Any combo of [password_chars] entries` |

# FILES

~/.config/keepmenu/config.ini

# AUTHOR

Scott Hansen - <tech@firecat53.net>

# COPYRIGHT

GNU General Public License 3

# SEE ALSO

Full documentation available at https://github.com/firecat53/keepmenu
