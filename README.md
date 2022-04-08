# Keepmenu

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/keepmenu)
![PyPI](https://img.shields.io/pypi/v/keepmenu)
![GitHub contributors](https://img.shields.io/github/contributors/firecat53/keepmenu)

Fully featured Dmenu/[Rofi][2]/[Bemenu][7]/[Wofi][8] frontend for autotype and managing of
Keepass databases.

Inspired in part by [Passhole][3], but more dmenu and less command line focused.

## Installation

`pip install --user keepmenu`

Ensure `~/.local/bin` is in your `$PATH`. Run `keepmenu` and enter your database
path, keyfile path, and password.

For full installation documention see the [installation docs][docs/install.md].

## Full Documentation

[Installation](docs/install.md) - [Configuration](docs/configure.md) - [Usage](docs/usage.md)

## Requirements

1. Python 3.7+
2. [Pykeepass][1] >= 4.0.0 and [pynput][5]
3. Dmenu, Rofi, Wofi or Bemenu
4. (optional) Pinentry
5. (optional) xdotool (for X), ydotool or wtype(for Wayland).

## Features

- Supports .kdbx databases, not .kdb.
- Auto-type username and/or password on selection. No clipboard copy/paste
  involved.
- Background process allows selectable time-out for locking the database.
- Multiple databases can be unlocked and switched on the fly.
- Use a custom [Keepass 2.x style auto-type sequence][6].
- Type, view or edit any field.
- Open the URL in the default web browser.
- Non U.S. English keyboard languages and layouts supported via xdotool or
  wtype(for Wayland).
- Edit notes using terminal or gui editor.
- Add and Delete entries.
- Add, delete, rename and move groups.
- Hide selected groups from the default and 'View/Type Individual entries' views.
- Configure the characters and groups of characters used during password
  generation.
- Optional Pinentry support for secure passphrase entry.
- [Keepass field references][4] are supported.
- Display and manage expired passwords.
- Add, edit and type TOTP codes.
- Add, edit, type and delete custom attributes.

## License

- GPLv3

## Usage

`keepmenu [-h] [-a AUTOTYPE] [-d DATABASE] [-k KEY_FILE]`

- Run `keepmenu` or bind to keystroke combination.
- Enter database path on first run.
- Start typing to match entries.
- [Configure](docs/configure.md) config.ini as desired.
- More detailed [usage information](docs/usage.md).

## Tests

To run tests in a venv: `make test`

## Development

- To install keepmen in a venv: `make`

- Build man page from Markdown source: `make man`

[1]: https://github.com/pschmitt/pykeepass "Pykeepass"
[2]: https://davedavenport.github.io/rofi/ "Rofi"
[3]: https://github.com/purduelug/passhole "Passhole"
[4]: https://keepass.info/help/base/fieldrefs.html "Keepass field references"
[5]: https://github.com/moses-palmer/pynput "pynput"
[6]: https://keepass.info/help/base/autotype.html#autoseq "Keepass 2.x codes"
[7]: https://github.com/Cloudef/bemenu "Bemenu"
[8]: https://hg.sr.ht/~scoopta/wofi "Wofi"
