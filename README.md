# Keepmenu

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/keepmenu)
![PyPI](https://img.shields.io/pypi/v/keepmenu)
![GitHub contributors](https://img.shields.io/github/contributors/firecat53/keepmenu)

Fully featured [Bemenu][7]/Dmenu/[Wmenu][14]/[Fuzzel][13]/[Rofi][2]/[Tofi][15]/[Wofi][8]/[Yofi][9] frontend for
autotype and managing of Keepass databases.

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
2. [Pykeepass][1] >= 4.0.0

Everything below is only needed for the interactive (launcher) mode. `--show`
works with nothing but Pykeepass installed:

3. [pynput][5] (`pip install keepmenu[autotype]`), or one of the alternate type
   libraries below
4. Bemenu, Dmenu, Wmenu, Fuzzel, Rofi, Tofi, Wofi, or Yofi
5. xsel or wl-copy, for clipboard support
6. (optional) Pinentry
7. (optional) xdotool (for X), [ydotool][10] or [wtype][11](for Wayland), [dotool][12] or dotoolc (X or Wayland).

## Features

- Supports .kdbx databases, not .kdb.
- Auto-type username and/or password on selection. Select to clipboard if
  desired (clears clipboard after 30s).
- Background process allows selectable time-out for locking the database.
- Multiple databases can be unlocked and switched on the fly.
- Use a custom [Keepass 2.x style auto-type sequence][6].
- Type, view or edit any field.
- Open the URL in the default web browser.
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
- Run once mode to copy or print any field(s) to stdout, usable as a CLI-only
  password manager with no launcher or GUI installed

## License

- GPLv3

## Usage

`keepmenu [-h] [-a AUTOTYPE] [-c CONF_FILE] [-C] [-d DATABASE] [-k KEY_FILE] [-t] [-n] [-s SEARCH] [-f FIELD] [-V]`

- Run `keepmenu` or bind to keystroke combination.
- Enter database path on first run.
- Start typing to match entries.
- [Configure](docs/configure.md) config.ini as desired.
- More detailed [usage information](docs/usage.md).

## Tests

To run tests in a venv: `make test`

## Development

- To install keepmenu in a venv: `make`
- Build man page from Markdown source: `make man`
- The version is hardcoded in `keepmenu/__init__.py` (`make version` or
  `keepmenu -V`). Anything else needing a version number reads from there.
- Using `hatch`:
    - `hatch shell`: provides venv with editable installation.
    - `hatch build` && `hatch publish`: build and publish to Pypi.
- Using `nix`:
    - `nix develop`: Provides development shell/venv with all dependencies.
    - `make test` and `hatch build/publish` work as usual.
- GitHub Action will upload to TestPyPi on each push to `main`. To create a
  GitHub and PyPi release, run `make release VERSION=x.y.z`. It bumps
  `__version__`, updates and rebuilds the man page, commits, and opens an
  editor for the annotated tag, prefilled with the version as the subject and
  one bullet per commit since the last tag.

        <tag name on first line, prefilled>

        * Release note 1
        * Release note 2
        * ...

  Then push the commit and tag: `git push origin main --follow-tags`. The
  GitHub Action fails the build if a pushed tag does not match `__version__`,
  so nothing mismatched can reach PyPi.

[1]: https://github.com/pschmitt/pykeepass "Pykeepass"
[2]: https://davedavenport.github.io/rofi/ "Rofi"
[3]: https://github.com/purduelug/passhole "Passhole"
[4]: https://keepass.info/help/base/fieldrefs.html "Keepass field references"
[5]: https://github.com/moses-palmer/pynput "pynput"
[6]: https://keepass.info/help/base/autotype.html#autoseq "Keepass 2.x codes"
[7]: https://github.com/Cloudef/bemenu "Bemenu"
[8]: https://hg.sr.ht/~scoopta/wofi "Wofi"
[9]: https://github.com/l4l/yofi "Yofi"
[10]: https://github.com/ReimuNotMoe/ydotool/ "Ydotool"
[11]: https://github.com/atx/wtype "Wtype"
[12]: https://git.sr.ht/~geb/dotool "Dotool"
[13]: https://codeberg.org/dnkl/fuzzel "Fuzzel"
[14]: https://git.sr.ht/~adnano/wmenu "wmenu"
[15]: https://github.com/philj56/tofi "Tofi"
