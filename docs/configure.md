# Keepmenu Configuration

[Installation](install.md) - [Usage](usage.md)

If you start keepmenu for the first time without a config file, it will prompt
you for database and keyfile locations and save them in a default config file.

OR Copy config.ini.example to ~/.config/keepmenu/config.ini and use it as a
reference for additional options.

Alternatively you can specify the file path to your config.ini using the -c/--config flag.

#### Config.ini values

| Section                   | Key                          | Default                                 | Notes                                                        |
|---------------------------|------------------------------|-----------------------------------------|--------------------------------------------------------------|
| `[dmenu]`                 | `dmenu_command`              | `dmenu`                                 | Command can include arguments                                |
|                           | `pinentry`                   | None                                    |                                                              |
|                           | `title_path`                 | `True`                                  | True, False or int                                           |
| `[dmenu_passphrase]`      | `obscure`                    | `False`                                 |                                                              |
|                           | `obscure_color`              | `#222222`                               | Only applicable to dmenu                                     |
| `[database]`              | `database_n`                 | None                                    | `n` is any integer                                           |
|                           | `keyfile_n`                  | None                                    |                                                              |
|                           | `password_n`                 | None                                    |                                                              |
|                           | `password_cmd_n`             | None                                    |                                                              |
|                           | `autotype_default_n`         | None                                    | Overrides global default                                     |
|                           | `pw_cache_period_min`        | `360`                                   | Value in minutes                                             |
|                           | `editor`                     | `vim`                                   |                                                              |
|                           | `terminal`                   | `xterm`                                 |                                                              |
|                           | `gui_editor`                 | None                                    |                                                              |
|                           | `type_library`               | `pynput`                                | xdotool, ydotool, wtype  or pynput                           |
|                           | `hide_groups`                | None                                    | See below for formatting of multiple groups                  |
|                           | `autotype_default`           | `{USERNAME}{TAB}{PASSWORD}{ENTER}`      | [Keepass autotype sequences][1]                              |
|                           | `type_url`                   | `False`                                 |                                                              |
| `[password_chars]`        | `lower`                      | `abcdefghijklmnopqrstuvwxyz`            |                                                              |
|                           | `upper`                      | `ABCDEFGHIJKLMNOPQRSTUVWXYZ`            |                                                              |
|                           | `digits`                     | `0123456789`                            |                                                              |
|                           | `punctuation`                | ``!"#$%%&'()*+,-./:;<=>?@[\]^_`{│}~``   |                                                              |
|                           | `Custom Name(s)`             | `Any string`                            |                                                              |
| `[password_char_presets]` | `Letters+Digits+Punctuation` | `upper lower digits punctuation`        |                                                              |
|                           | `Letters+Digits`             | `upper lower digits`                    |                                                              |
|                           | `Letters`                    | `upper lower`                           |                                                              |
|                           | `Digits`                     | `digits`                                |                                                              |
|                           | `Custom Name(s)`             | `Any combo of [password_chars] entries` |                                                              |

#### Config.ini example

    [dmenu]
    # Note that dmenu_command can contain arguments as well
    dmenu_command = rofi -dmenu -theme keepmenu -i
    # dmenu_command = dmenu -i -l 25 -b -nb #909090 -nf #303030
    pinentry = pinentry-gtk
    title_path = 25

    [dmenu_passphrase]
    ## Obscure password entry.
    obscure = True
    obscure_color = #303030

    [database]
    database_1 = ~/docs/Passwords.kdbx
    keyfile_1 = /mnt/usb/keyfile
    database_2 = ~/docs/totp_db.kdbx
    autotype_default_2 = {TOTP}{ENTER}
    password_cmd_2 = gpg -qd ~/.pass.gpg

    pw_cache_period_min = 720

    gui_editor = gvim -f
    type_library = xdotool
    hide_groups = Recycle Bin
                  Group 2
                  Group 3
    type_url = True

    ## Set the global default
    autotype_default = {USERNAME}{TAB}{PASSWORD}{ENTER}

    [password_chars]
    # Set custom groups of characters for password generation. Any name is fine and
    # these can be used to create new groups of presets in password_char_presets. If
    # you reuse 'upper', 'lower', 'digits', or 'punctuation', those will
    # replace the default values.
    lower = abcdefghjkmnpqrstuvwxyz
    upper = ABCDEFGHJKMNPQRSTUVWXYZ
    digits = 23456789
    punctuation = !"#$%%&'()*+,-./:;<=>?@[\]^_`{}~
    # NOTE: % needs to be escaped with another % sign
    # Custom EXAMPLES:
    punc min = !?#*@-+$%%
    upper = ABCDEFZ

    [password_char_presets]
    # Set character preset groups for password generation. For multiple sets use a space in between
    # If you set any custom presets here, the default sets will not be displayed unless uncommented below:
    # Valid values are: upper lower digits punctuation
    # Also valid are any custom sets defined in [password_chars]
    # Custom Examples:
    Minimal Punc = upper lower digits "punc min"
    Router Site = upper digits

1. Add your database(s) and keyfile(s)
2. Adjust `pw_cache_period_min` if desired. Default is 6 hours (360 min).
3. Set the dmenu_command to the desired application, including configuration
   options.
   - *Note:* If using wofi, the `--height` paramater will not work properly. You
     will have to set `--lines` instead, as keepmenu attempts to set a dynamic
     height based on number of lines of options.
   - If using Rofi, pass desired theme via `dmenu_command = rofi -theme
     <theme>.rasi`.
   - Dmenu theme options are also passed in `dmenu_command`
5. Adjust the `autotype_default`, if desired. Allowed codes are the [Keepass 2.x
   codes][1] except for repetitions and most command codes. `{DELAY x}`
   (in milliseconds) is supported. Individual autotype sequences can be edited
   or disabled inside Keepmenu.
6. If you need support on Wayland for non-U.S. English keyboard layouts and/or
   characters, you might need to experiment with the various typing options to
   which works for your use case.

    * When using xdotool, call `setxkbmap` to set your keyboard type somewhere
      in your window manager or desktop environment initialization. For example:
      `exec setxkbmap de` in ~/.config/i3/config.

7. New sets of characters can be set in config.ini in the `[password_chars]`
   section. A new preset for each custom set will be listed in addition to the
   default presets. If you redefine one of the default sets (upper, lower,
   digits, punctuation), it will replace the default values.
8. New preset groups of character sets can be defined in config.ini in the
   `[password_char_presets]` section. You can set any combination of default and
   custom character sets. A minimum of one character from each distinct set will
   be used when generating a new password. If any custom presets are defined,
   the default presets will not be displayed unless they are uncommented.

**Warning** If you choose to store your database password into config.ini, make
sure to `chmod 600 config.ini`. This is not secure and I only added it as a
convenience for testing.

[1]:  https://keepass.info/help/base/autotype.html#autoseq "Keepass Autotype Sequences"
