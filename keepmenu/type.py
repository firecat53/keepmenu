"""Methods for typing entries with pynput, xdotool, ydotool, wtype, dotool

"""
# flake8: noqa
# pylint: disable=import-outside-toplevel
import re
from shlex import split
from subprocess import call, run, CalledProcessError, DEVNULL, Popen
import sys
from threading import Timer
import time

import keepmenu
from keepmenu.menu import dmenu_err
from keepmenu.totp import gen_otp, get_otp_url


# Module-level variable to track the current delay override from {DELAY=x} token
_current_delay = None

PYNPUT_MISSING = ("pynput is not installed.\n"
                  "Install it with `pip install keepmenu[autotype]` or set "
                  "`type_library` in config.ini to a supported type_library "
                  "(see docs).")


def _get_key_delay():
    """Get key_delay from config in milliseconds, or None"""
    return keepmenu.CONF.get('database', 'key_delay', fallback=None)


def _effective_delay():
    """Return the effective key delay: {SPEED} override > config > None"""
    return _current_delay if _current_delay is not None else _get_key_delay()


def tokenize_autotype(autotype):
    """Process the autotype sequence

    Args: autotype - string
    Returns: tokens - generator ((token, if_special_char T/F), ...)

    """
    while autotype:
        opening_idx = -1
        for char in "{+^%~@":
            idx = autotype.find(char)
            if idx != -1 and (opening_idx == -1 or idx < opening_idx):
                opening_idx = idx

        if opening_idx == -1:
            # found the end of the string without further opening braces or
            # other characters
            yield autotype, False
            return

        if opening_idx > 0:
            yield autotype[:opening_idx], False

        if autotype[opening_idx] in "+^%~@":
            yield autotype[opening_idx], True
            autotype = autotype[opening_idx + 1:]
            continue

        closing_idx = autotype.find('}')
        if closing_idx == -1:
            dmenu_err("Unable to find matching right brace (}) while" +
                      f"tokenizing auto-type string: {autotype}\n")
            return
        if closing_idx == opening_idx + 1 and closing_idx + 1 < len(autotype) \
                and autotype[closing_idx + 1] == '}':
            yield "{}}", True
            autotype = autotype[closing_idx + 2:]
            continue
        yield autotype[opening_idx:closing_idx + 1], True
        autotype = autotype[closing_idx + 1:]


def token_command(token):
    """When token denotes a special command, this function provides a callable
    implementing its behaviour.

    """
    cmd = None

    def _check_delay():
        match = re.match(r'{DELAY (\d+)}', token)
        if match:
            delay = match.group(1)
            nonlocal cmd
            cmd = lambda _, t=delay: time.sleep(int(t) / 1000)
            return True
        return False

    def _check_delay_equals():
        match = re.match(r'{DELAY=(\d+)}', token)
        if match:
            delay_eq = int(match.group(1))
            nonlocal cmd
            def set_delay(_, s=delay_eq):
                global _current_delay
                _current_delay = str(s) if s > 0 else None
            cmd = set_delay
            return True
        return False

    def _check_additional_attribute():
        match = re.match(r'{S:(.*)}', token)
        if match:
            attr = match.group(1)
            nonlocal cmd
            cmd = lambda e, a=attr: e.get_custom_property(a)
            return True
        return False

    if _check_delay():  # {DELAY x}
        return cmd

    if _check_delay_equals():  # {DELAY=x}
        return cmd

    if _check_additional_attribute():  # {S:<attr>}
        return cmd

    return None


def type_entry(entry, db_autotype=None):
    """Pick which library to use to type strings

    Defaults to pynput

    Args: entry - The entry to type
          db_autotype - the database specific autotype that overrides 'autotype_default'

    """
    global _current_delay
    _current_delay = None
    sequence = keepmenu.SEQUENCE
    if keepmenu.CLIPBOARD is True:
        if hasattr(entry, 'password'):
            if not type_clipboard(entry.password):
                dmenu_err(keepmenu.clipboard_missing_msg())
        else:
            dmenu_err("Clipboard is active. 'View/Type Individual entries' and select field to copy")
        return
    if hasattr(entry, 'autotype_enabled') and entry.autotype_enabled is False:
        dmenu_err("Autotype disabled for this entry")
        return
    if db_autotype is not None and db_autotype != '':
        sequence = db_autotype
    if hasattr(entry, 'autotype_sequence') and \
            entry.autotype_sequence is not None and \
            entry.autotype_sequence != 'None':
        sequence = entry.autotype_sequence
    tokens = tokenize_autotype(sequence)

    libraries = {'pynput': type_entry_pynput,
                 'xdotool': type_entry_xdotool,
                 'ydotool': type_entry_ydotool,
                 'wtype': type_entry_wtype,
                 'dotool': type_entry_dotool,
                 'dotoolc': type_entry_dotoolc}
    library = keepmenu.CONF.get('database', 'type_library', fallback='pynput')
    libraries.get(library, type_entry_pynput)(entry, tokens)

PLACEHOLDER_AUTOTYPE_TOKENS = {
    "{TITLE}"   : lambda e: keepmenu.safe_deref(e, 'title'),
    "{USERNAME}": lambda e: keepmenu.safe_deref(e, 'username'),
    "{URL}"     : lambda e: keepmenu.safe_deref(e, 'url'),
    "{PASSWORD}": lambda e: keepmenu.safe_deref(e, 'password'),
    "{NOTES}"   : lambda e: keepmenu.safe_deref(e, 'notes'),
    "{TOTP}"    : lambda e: gen_otp(get_otp_url(e)),
    "{TIMEOTP}" : lambda e: gen_otp(get_otp_url(e)),
}

STRING_AUTOTYPE_TOKENS = {
    "{PLUS}"      : '+',
    "{PERCENT}"   : '%',
    "{CARET}"     : '^',
    "{TILDE}"     : '~',
    "{LEFTPAREN}" : '(',
    "{RIGHTPAREN}": ')',
    "{LEFTBRACE}" : '{',
    "{RIGHTBRACE}": '}',
    "{AT}"        : '@',
    "{+}"         : '+',
    "{%}"         : '%',
    "{^}"         : '^',
    "{~}"         : '~',
    "{(}"         : '(',
    "{)}"         : ')',
    "{[}"         : '[',
    "{]}"         : ']',
    "{{}"         : '{',
    "{}}"         : '}',
}


def _pynput_type(kbd, to_type):
    """Type a string using pynput with optional delay between characters"""
    delay = _effective_delay()
    if delay is not None:
        delay_sec = int(delay) / 1000
        for char in to_type:
            kbd.type(char)
            time.sleep(delay_sec)
    else:
        kbd.type(to_type)


def type_entry_pynput(entry, tokens):  # pylint: disable=too-many-branches
    """Use pynput to auto-type the selected entry

    """
    try:
        from pynput import keyboard
        from .tokens_pynput import AUTOTYPE_TOKENS
    except ModuleNotFoundError:
        dmenu_err(PYNPUT_MISSING)
        return
    kbd = keyboard.Controller()
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                to_type = cmd(entry)  # pylint: disable=not-callable
                if to_type is not None:
                    try:
                        _pynput_type(kbd, to_type)
                    except kbd.InvalidCharacterException:
                        dmenu_err("Unable to type string...bad character.\n"
                                  "Try setting `type_library = xdotool` in config.ini")
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    try:
                        _pynput_type(kbd, to_type)
                    except kbd.InvalidCharacterException:
                        dmenu_err("Unable to type string...bad character.\n"
                                  "Try setting `type_library = xdotool` in config.ini")
                        return
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                try:
                    _pynput_type(kbd, to_type)
                except kbd.InvalidCharacterException:
                    dmenu_err("Unable to type string...bad character.\n"
                              "Try setting `type_library = xdotool` in config.ini")
                    return
            elif token in AUTOTYPE_TOKENS:
                to_tap = AUTOTYPE_TOKENS[token]
                kbd.tap(to_tap)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    kbd.tap(to_tap)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (pynput): \"{token}\"")
                return
        else:
            try:
                _pynput_type(kbd, token)
            except kbd.InvalidCharacterException:
                dmenu_err("Unable to type string...bad character.\n"
                          "Try setting `type_library = xdotool` in config.ini")
                return


def _xdotool_type(to_type):
    """Type a string using xdotool with optional --delay"""
    cmd = ['xdotool', 'type']
    delay = _effective_delay()
    if delay is not None:
        cmd.extend(['--delay', delay])
    cmd.extend(['--', to_type])
    call(cmd)


def type_entry_xdotool(entry, tokens):
    """Auto-type entry entry using xdotool

    """
    enter_idx = True
    from .tokens_xdotool import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                to_type = cmd(entry)  # pylint: disable=not-callable
                if to_type is not None:
                    _xdotool_type(to_type)
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    _xdotool_type(to_type)
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                _xdotool_type(to_type)
            elif token in AUTOTYPE_TOKENS:
                cmd = ['xdotool'] + AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['xdotool'] + AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (xdotool): \"{token}\"")
                return
        else:
            _xdotool_type(token)


def _ydotool_type(to_type):
    """Type a string using ydotool with optional --key-delay"""
    cmd = ['ydotool', 'type', '-e', '0']
    delay = _effective_delay()
    if delay is not None:
        cmd.extend(['--key-delay', delay])
    cmd.extend(['--', to_type])
    call(cmd)


def type_entry_ydotool(entry, tokens):
    """Auto-type entry entry using ydotool

    """
    from .tokens_ydotool import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                to_type = cmd(entry)  # pylint: disable=not-callable
                if to_type is not None:
                    _ydotool_type(to_type)
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    _ydotool_type(to_type)
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                _ydotool_type(to_type)
            elif token in AUTOTYPE_TOKENS:
                cmd = ['ydotool'] + AUTOTYPE_TOKENS[token]
                call(cmd)
            else:
                dmenu_err(f"Unsupported auto-type token (ydotool): \"{token}\"")
                return
        else:
            _ydotool_type(token)


def _wtype_type(to_type):
    """Type a string using wtype with optional -d delay"""
    cmd = ['wtype']
    delay = _effective_delay()
    if delay is not None:
        cmd.extend(['-d', delay])
    cmd.extend(['--', to_type])
    call(cmd)


def type_entry_wtype(entry, tokens):
    """Auto-type entry entry using wtype

    """
    from .tokens_wtype import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                to_type = cmd(entry)  # pylint: disable=not-callable
                if to_type is not None:
                    _wtype_type(to_type)
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    _wtype_type(to_type)
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                _wtype_type(to_type)
            elif token in AUTOTYPE_TOKENS:
                cmd = ['wtype', '-k', AUTOTYPE_TOKENS[token]]
                call(cmd)
            else:
                dmenu_err(f"Unsupported auto-type token (wtype): \"{token}\"")
                return
        else:
            _wtype_type(token)


def _dotool_type(to_type, client=False):
    """Type a string using dotool/dotoolc with optional typedelay

    dotool reads one command per line from stdin, so a value containing a
    newline would turn its own remaining lines into dotool commands. Send each
    line as its own "type" command and press enter between them instead.
    """
    tool = 'dotoolc' if client else 'dotool'
    delay = _effective_delay()
    cmds = []
    if delay is not None:
        cmds.append(f"typedelay {delay}")
    lines = to_type.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for idx, line in enumerate(lines):
        if idx:
            cmds.append("key enter")
        if line:
            cmds.append(f"type {line}")
    if not cmds:
        return
    _ = run([tool], check=True, encoding=keepmenu.ENC, input="\n".join(cmds))


def type_entry_dotool(entry, tokens):
    """Auto-type entry entry using dotool

    """
    from .tokens_dotool import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                to_type = cmd(entry)  # pylint: disable=not-callable
                if to_type is not None:
                    _dotool_type(to_type)
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    _dotool_type(to_type)
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                _dotool_type(to_type)
            elif token in AUTOTYPE_TOKENS:
                to_type = " ".join(AUTOTYPE_TOKENS[token])
                _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=to_type)
            else:
                dmenu_err(f"Unsupported auto-type token (dotool): \"{token}\"")
                return
        else:
            _dotool_type(token)


def type_entry_dotoolc(entry, tokens):
    """Auto-type entry entry using dotoolc (client for dotoold daemon)

    """
    from .tokens_dotool import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                to_type = cmd(entry)  # pylint: disable=not-callable
                if to_type is not None:
                    _dotool_type(to_type, client=True)
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    _dotool_type(to_type, client=True)
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                _dotool_type(to_type, client=True)
            elif token in AUTOTYPE_TOKENS:
                to_type = " ".join(AUTOTYPE_TOKENS[token])
                _ = run(['dotoolc'], check=True, encoding=keepmenu.ENC, input=to_type)
            else:
                dmenu_err(f"Unsupported auto-type token (dotoolc): \"{token}\"")
                return
        else:
            _dotool_type(token, client=True)


def type_text(data):
    """Type the given text data

    """
    if keepmenu.CLIPBOARD is True:
        if not type_clipboard(data):
            dmenu_err(keepmenu.clipboard_missing_msg())
        return
    library = 'pynput'
    if keepmenu.CONF.has_option('database', 'type_library'):
        library = keepmenu.CONF.get('database', 'type_library')
    if library == 'xdotool':
        _xdotool_type(data)
    elif library == 'ydotool':
        _ydotool_type(data)
    elif library == 'wtype':
        _wtype_type(data)
    elif library == 'dotool':
        _dotool_type(data)
    elif library == 'dotoolc':
        _dotool_type(data, client=True)
    else:
        try:
            from pynput import keyboard
        except ModuleNotFoundError:
            dmenu_err(PYNPUT_MISSING)
            return
        kbd = keyboard.Controller()
        try:
            _pynput_type(kbd, data)
        except kbd.InvalidCharacterException:
            dmenu_err("Unable to type string...bad character.\n"
                      "Try setting `type_library = xdotool` in config.ini")


CLIPBOARD_CLEAR_SEC = 30


def clear_clipboard_later(cmd):
    """Clear the clipboard after CLIPBOARD_CLEAR_SEC seconds

    The daemon sticks around long enough to do this on a timer thread, but a
    one-shot --show exits as soon as it has copied, which would kill the timer
    and leave the password in the clipboard for good. Hand that case off to a
    detached child so the shell still gets its prompt back immediately.

    Args: cmd - str, clipboard command

    """
    if keepmenu.CLI is not True:
        clear = Timer(CLIPBOARD_CLEAR_SEC,
                      lambda: run(split(cmd), check=False, input=""))
        clear.daemon = True
        clear.start()
        return
    Popen([sys.executable, "-c",
           "import subprocess, sys, time\n"
           "time.sleep(float(sys.argv[1]))\n"
           "subprocess.run(sys.argv[2:], check=False, input=b'')\n",
           str(CLIPBOARD_CLEAR_SEC), *split(cmd)],
          start_new_session=True,
          stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)  # pylint: disable=consider-using-with


def type_clipboard(text):
    """Copy text to clipboard and clear clipboard after 30 seconds

    Args: text - str
    Returns: bool - False if no clipboard command is available

    """
    cmd = keepmenu.get_clipboard_cmd()
    if cmd is None:
        return False
    text = text or ""  # Handle None type
    try:
        run(split(cmd), check=True, input=text.encode(keepmenu.ENC))
    except CalledProcessError:
        return False
    clear_clipboard_later(cmd)
    return True
