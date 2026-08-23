# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make                 # create .venv and editable-install '.[autotype]'
make test            # run the full suite (tests/tests.py, plain unittest)
make man             # regenerate keepmenu.1 from keepmenu.1.md (needs pandoc)
make version         # print __version__
make release VERSION=x.y.z   # bump version, rebuild man page, commit, annotated tag
nix develop          # dev shell with uv/hatch/pandoc; make test works inside
```

Run a single test or class (must be run from the repo root — tests use relative
paths like `tests/keepmenu-config.ini`):

```bash
.venv/bin/python tests/tests.py TestFunctions.test_generate_password
.venv/bin/python tests/tests.py TestCli
```

The version is hardcoded in `keepmenu/__init__.py`; everything else (hatch, the
flake, CI's tag check) reads it from there.

## Architecture

Keepmenu runs in two very different modes, and most bugs come from confusing them.

**Daemon mode (the launcher/GUI path).** `keepmenu/__main__.py:main` looks for
an auth file (`$XDG_RUNTIME_DIR/keepmenu/.keepmenu-auth`, else
`$TMPDIR/keepmenu-<uid>/`) holding a port and authkey. If a daemon answers on
that port, this invocation is a *client*: it sends the parsed args over a
`multiprocessing` `Pipe` and sets flags on the daemon's `Server` (a
`BaseManager` RPC). If no daemon answers, `run()` starts one: a `Server`
process plus a `DmenuRunner` process (`keepmenu/keepmenu.py`), which holds the
decrypted `PyKeePass` objects in `self.open_databases` and loops on
`server.start_flag`.

Because the RPC is pickle-based, the authkey is what keeps another local user
out of the daemon — it must stay a CSPRNG value. Connections are wrapped in
`port_in_use`/`connect_to_daemon`/`time_limit` so a stale auth file whose port
was reused can't hang keepmenu; that machinery is deliberate, not incidental.

**One-shot mode (`--show`, no daemon).** `keepmenu/run_once.py:run_once` opens
the database directly and prints fields. This path needs nothing but pykeepass
— no launcher, no type library.

Client and daemon are **separate processes with separate stdio**. The daemon
can never prompt on the CLI. Anything the user must type (a password) is
collected in the client (`main()`) and passed through the args pipe; results
travel back over the same pipe (`Server.receive_show_result` ←
`DmenuRunner.show_password`). `shared_state` (a `multiprocessing.Manager`
namespace) publishes read-only facts the client needs *before* deciding whether
to prompt: which databases are unlocked, and which have a password or
`password_cmd` in config.

### --show behavior (the rules this must satisfy)

1. Daemon not running: prompt for the password on the CLI if it isn't already in config.ini.
2. Daemon running: prompt on the CLI *only* if the database isn't already unlocked (not in `self.open_databases`). Never use the GUI prompt.
3. When the daemon is running and a password was entered on the CLI, that database also gets opened in the GUI (added to `self.open_databases`).
4. Remember the server/client split above when adding to this path.

### Module map

- `keepmenu/__init__.py` — module-level globals (`CONF`, `SEQUENCE`, `CLIPBOARD`,
  `CACHE_PERIOD_MIN`, `MAX_LEN`, `CLI`), `reload_config()`, runtime-dir and
  permission checks. Config changes go through `reload_config`, which mutates
  those globals; tests call it with a temp path.
- `keepmenu/keepmenu.py` — `DataBase` dataclass, database opening/selection
  (`get_database`), and `DmenuRunner` with one `menu_*` method per top-level
  menu item.
- `keepmenu/menu.py` — builds the launcher argv. Per-launcher flags live in the
  `commands` dict in `dmenu_cmd`; a second dict handles password-obscuring
  flags. Adding launcher support means adding entries here.
- `keepmenu/type.py` — autotype. `tokenize_autotype` splits a sequence,
  `token_command` handles `{DELAY x}`, `{DELAY=x}`, `{S:<attr>}`, and
  `type_entry` dispatches to one `type_entry_<library>` per backend
  (pynput/xdotool/ydotool/wtype/dotool/dotoolc) selected by
  `database.type_library`. Each backend has a matching `tokens_<library>.py`
  mapping token → that library's key representation, so a new token must be
  added to *every* token table plus `PLACEHOLDER_AUTOTYPE_TOKENS` /
  `STRING_AUTOTYPE_TOKENS`.
- `keepmenu/view.py`, `keepmenu/edit.py` — read-only views and all mutating
  operations (entries, groups, notes, TOTP, custom attributes, password gen).
- `keepmenu/totp.py` — self-contained HOTP/TOTP (incl. Steam), reads both the
  `otp` URL field and the KeePass 2.x `TimeOtp-*` fields.

Only use standard KeePass 2.x autotype tokens
(https://keepass.info/help/base/autotype.html#autoseq). Don't invent new token
names.

## Tests

`tests/tests.py` is a single unittest module (no pytest, no `__init__.py`). It
covers the daemon handshake and auth file, the CLI/`--show` paths, config
parsing, tokenizing, TOTP and clipboard. Fixtures: `tests/test.kdbx` (password
`password`) and `tests/keepmenu-config.ini`. Tests that touch config set
`KM.CONF_FILE` to a temp dir and call `KM.reload_config()` — do the same rather
than writing to the real `~/.config/keepmenu/config.ini`.

## Conventions

- Create feature branches from `develop`, not `main`.
- CI (`.github/workflows/main.yml`) publishes every push to `main` to TestPyPI
  with a `.devN` suffix, and tags to PyPI. A tag that disagrees with
  `__version__` fails the build.
