"""Set global variables. Read the config file. Create default config file if one
doesn't exist.

"""
import configparser
import locale
import os
import shlex
from subprocess import run, DEVNULL
import sys
from os.path import exists, expanduser

from keepmenu.menu import dmenu_err

# Setup logging for debugging. Usage: logger.info(...)
# import logging
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
# file_handler = logging.FileHandler('keepmenu.log', mode='w')
# formatter = logging.Formatter('%(message)s')
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)

AUTH_FILE = expanduser("~/.cache/.keepmenu-auth")
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
CLIPBOARD_CMD = "true"


def reload_config(conf_file = None):  # pylint: disable=too-many-statements,too-many-branches
    """Reload config file. Primarly for use with tests and the --config flag.

    Args: conf_file - os.path

    """
    # pragma pylint: disable=global-statement,global-variable-not-assigned
    global CACHE_PERIOD_MIN, \
        CACHE_PERIOD_DEFAULT_MIN, \
        CLIPBOARD_CMD, \
        CONF, \
        MAX_LEN, \
        ENV, \
        ENC, \
        SEQUENCE
    # pragma pylint: enable=global-variable-undefined,global-variable-not-assigned
    CONF = configparser.ConfigParser()
    conf_file = conf_file if conf_file is not None else CONF_FILE
    if not exists(conf_file):
        try:
            os.mkdir(os.path.dirname(conf_file))
        except OSError:
            pass
        with open(conf_file, 'w', encoding=ENC) as cfile:
            CONF.add_section('dmenu')
            CONF.set('dmenu', 'dmenu_command', 'dmenu')
            CONF.add_section('dmenu_passphrase')
            CONF.set('dmenu_passphrase', 'obscure', 'True')
            CONF.set('dmenu_passphrase', 'obscure_color', '#222222')
            CONF.add_section('database')
            CONF.set('database', 'database_1', '')
            CONF.set('database', 'keyfile_1', '')
            CONF.set('database', 'pw_cache_period_min', str(CACHE_PERIOD_DEFAULT_MIN))
            CONF.set('database', 'autotype_default', SEQUENCE)
            CONF.write(cfile)
    try:
        CONF.read(conf_file)
    except configparser.ParsingError as err:
        dmenu_err(f"Config file error: {err}")
        sys.exit()
    if CONF.has_option('dmenu', 'dmenu_command'):
        command = shlex.split(CONF.get('dmenu', 'dmenu_command'))
    else:
        CONF.set('dmenu', 'dmenu_command', 'dmenu')
        command = 'dmenu'
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
    if os.environ.get('WAYLAND_DISPLAY'):
        clips = ['wl-copy -o']
    else:
        clips = ["xsel -b", "xclip -l 1 -selection clip"]
    for clip in clips:
        try:
            _ = run(shlex.split(clip), check=False, stdout=DEVNULL, stderr=DEVNULL, input="")
            CLIPBOARD_CMD = clip
            break
        except OSError:
            continue
    if CLIPBOARD_CMD == "true":
        dmenu_err(f"{' or '.join([shlex.split(i)[0] for i in clips])} needed for clipboard support")


# vim: set et ts=4 sw=4 :
