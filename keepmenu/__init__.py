"""Set global variables. Read the config file. Create default config file if one
doesn't exist.

"""
import configparser
import locale
import os
import shlex
import shutil
from subprocess import run, DEVNULL
import sys
import tempfile
from os.path import exists, expanduser, join

from keepmenu.menu import dmenu_err

__version__ = "1.5.1"


# Setup logging for debugging. Usage: logger.info(...)
# import logging
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
# file_handler = logging.FileHandler('keepmenu.log', mode='w')
# formatter = logging.Formatter('%(message)s')
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)


def get_runtime_dir():
    """Get the runtime directory for auth file storage.

    Prefers $XDG_RUNTIME_DIR/keepmenu/. Falls back to $TMPDIR/keepmenu-<uid>/ 

    Returns: str path to runtime directory

    """
    xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
    if xdg_runtime and exists(xdg_runtime):
        runtime_dir = join(xdg_runtime, 'keepmenu')
    else:
        runtime_dir = join(tempfile.gettempdir(), f'keepmenu-{os.getuid()}')
    if not exists(runtime_dir):
        os.makedirs(runtime_dir, mode=0o700)
    return runtime_dir


AUTH_FILE = join(get_runtime_dir(), ".keepmenu-auth")
CONF_FILE = expanduser("~/.config/keepmenu/config.ini")
SECRET_VALID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

ENV = os.environ.copy()
ENC = locale.getpreferredencoding()
CACHE_PERIOD_DEFAULT_MIN = 360
CACHE_PERIOD_MIN = CACHE_PERIOD_DEFAULT_MIN
SEQUENCE = "{USERNAME}{TAB}{PASSWORD}{ENTER}"
MAX_LEN = 24
CONF = configparser.ConfigParser()
CLIPBOARD = False
CLIPBOARD_CMD = None
# True when running non-interactively (--show), so errors go to stderr instead
# of to a dmenu style launcher, which may not be installed at all.
CLI = False


def default_conf():
    """Contents of the config file generated on first run.

    database_1/keyfile_1 are commented out examples rather than empty values so
    that a fresh config doesn't look like it holds a broken database entry.
    Written as text because configparser can't emit comments.

    Returns: str

    """
    return ("[dmenu]\n"
            "dmenu_command = dmenu\n"
            "\n"
            "[dmenu_passphrase]\n"
            "obscure = True\n"
            "obscure_color = #222222\n"
            "\n"
            "[database]\n"
            "# database_1 = ~/passwords.kdbx\n"
            "# keyfile_1 = ~/passwords.key\n"
            f"pw_cache_period_min = {CACHE_PERIOD_DEFAULT_MIN}\n"
            f"autotype_default = {SEQUENCE}\n")


def get_clipboard_cmd():
    """Find an available clipboard command.

    Detected on first use rather than at config load so that keepmenu works on
    systems with no clipboard tool installed. The result is cached in
    CLIPBOARD_CMD.

    Returns: str command or None if no clipboard tool is available

    """
    global CLIPBOARD_CMD  # pylint: disable=global-statement
    if CLIPBOARD_CMD is not None:
        return CLIPBOARD_CMD
    clips = ['wl-copy'] if os.environ.get('WAYLAND_DISPLAY') else \
        ["xsel -b", "xclip -selection clip"]
    for clip in clips:
        try:
            _ = run(shlex.split(clip), check=False, stdout=DEVNULL, stderr=DEVNULL, input="")
        except OSError:
            continue
        CLIPBOARD_CMD = clip
        return CLIPBOARD_CMD
    return None


def clipboard_missing_msg():
    """Error message naming the clipboard commands keepmenu looks for

    Returns: str

    """
    clips = ['wl-copy'] if os.environ.get('WAYLAND_DISPLAY') else ["xsel", "xclip"]
    return f"{' or '.join(clips)} needed for clipboard support"


def reload_config(conf_file = None):  # pylint: disable=too-many-statements,too-many-branches
    """Reload config file. Primarly for use with tests and the --config flag.

    Args: conf_file - os.path

    """
    # pragma pylint: disable=global-statement,global-variable-not-assigned
    global CACHE_PERIOD_MIN, \
        CACHE_PERIOD_DEFAULT_MIN, \
        CONF, \
        MAX_LEN, \
        ENV, \
        ENC, \
        SEQUENCE
    # pragma pylint: enable=global-variable-undefined,global-variable-not-assigned
    CONF = configparser.ConfigParser()
    conf_file = conf_file if conf_file is not None else CONF_FILE
    if not exists(conf_file):
        conf_dir = os.path.dirname(conf_file)
        if conf_dir:
            os.makedirs(conf_dir, exist_ok=True)
        with open(conf_file, 'w', encoding=ENC) as cfile:
            cfile.write(default_conf())
    try:
        CONF.read(conf_file)
    except configparser.Error as err:
        dmenu_err(f"Config file error: {err}")
        sys.exit()
    # Add empty config sections
    for section in ('dmenu', 'dmenu_passphrase', 'database'):
        if not CONF.has_section(section):
            CONF.add_section(section)
    command = shlex.split(CONF.get('dmenu', 'dmenu_command', fallback='dmenu'))
    if "-l" in command:
        MAX_LEN = int(command[command.index("-l") + 1])
    if CONF.has_option("database", "pw_cache_period_min"):
        CACHE_PERIOD_MIN = int(CONF.get("database", "pw_cache_period_min"))
    else:
        CACHE_PERIOD_MIN = CACHE_PERIOD_DEFAULT_MIN
    if CONF.has_option('database', 'autotype_default'):
        SEQUENCE = CONF.get("database", "autotype_default")
    if CONF.has_option("database", "type_library"):
        for typ in ["xdotool", "ydotool", "wtype", "dotool"]:
            if CONF.get("database", "type_library") == typ:
                try:
                    _ = run([typ, "--version"], check=False, stdout=DEVNULL, stderr=DEVNULL)
                except OSError:
                    dmenu_err(f"{typ} not installed.\n"
                              "Please install or remove that option from config.ini")
                    sys.exit()
        if CONF.get("database", "type_library") == "dotoolc":
            if shutil.which("dotoolc") is None:
                dmenu_err("dotoolc not installed.\n"
                          "Please install or remove that option from config.ini")
                sys.exit()


def safe_deref(entry, field):
    """Safely dereference an entry field, handling cases where referenced fields are None.

    When an entry has a field reference (e.g., {REF:U@I:target}) and the target field
    is None/empty, pykeepass's deref raises a TypeError. This wrapper catches that
    error and returns an empty string.

    Args:
        entry: KeePass entry object
        field: Field name to dereference (e.g., 'username', 'password', 'title')

    Returns:
        str: Dereferenced field value or empty string if None or error

    """
    try:
        return entry.deref(field) or ""
    except TypeError:
        # Handle case where referenced field is None
        return ""

# vim: set et ts=4 sw=4 :
