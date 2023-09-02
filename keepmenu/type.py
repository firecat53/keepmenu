"""Methods for typing entries with pynput, xdotool, ydotool, wtype, dotool

"""
# flake8: noqa
# pylint: disable=import-outside-toplevel
import re
from shlex import split
from subprocess import call, run
from threading import Timer
import time

import keepmenu
from keepmenu.menu import dmenu_err
from keepmenu.totp import gen_otp, get_otp_url


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

    if _check_additional_attribute():  # {S:<attr>}
        return cmd

    return None


def type_entry(entry, db_autotype=None):
    """Pick which library to use to type strings

    Defaults to pynput

    Args: entry - The entry to type
          db_autotype - the database specific autotype that overrides 'autotype_default'

    """
    sequence = keepmenu.SEQUENCE
    if keepmenu.CLIPBOARD is True:
        if hasattr(entry, 'password'):
            type_clipboard(entry.password)
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

    library = "pynput"
    libraries = {'pynput': type_entry_pynput,
                 'xdotool': type_entry_xdotool,
                 'ydotool': type_entry_ydotool,
                 'wtype': type_entry_wtype,
                 'dotool': type_entry_dotool}
    library = keepmenu.CONF.get('database', 'type_library', fallback='pynput')
    libraries.get(library, type_entry_pynput)(entry, tokens)

PLACEHOLDER_AUTOTYPE_TOKENS = {
    "{TITLE}"   : lambda e: e.deref('title'),
    "{USERNAME}": lambda e: e.deref('username'),
    "{URL}"     : lambda e: e.deref('url'),
    "{PASSWORD}": lambda e: e.deref('password'),
    "{NOTES}"   : lambda e: e.deref('notes'),
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

def type_entry_pynput(entry, tokens):  # pylint: disable=too-many-branches
    """Use pynput to auto-type the selected entry

    """
    try:
        from pynput import keyboard
        from .tokens_pynput import AUTOTYPE_TOKENS
    except ModuleNotFoundError:
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
                        kbd.type(to_type)
                    except kbd.InvalidCharacterException:
                        dmenu_err("Unable to type string...bad character.\n"
                                  "Try setting `type_library = xdotool` in config.ini")
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    try:
                        kbd.type(to_type)
                    except kbd.InvalidCharacterException:
                        dmenu_err("Unable to type string...bad character.\n"
                                  "Try setting `type_library = xdotool` in config.ini")
                        return
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                try:
                    kbd.type(to_type)
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
                kbd.type(token)
            except kbd.InvalidCharacterException:
                dmenu_err("Unable to type string...bad character.\n"
                          "Try setting `type_library = xdotool` in config.ini")
                return


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
                    call(['xdotool', 'type', '--', to_type])
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['xdotool', 'type', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['xdotool', 'type', '--', to_type])
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
            call(['xdotool', 'type', '--', token])


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
                    call(['ydotool', 'type', '-e', '0', '--', to_type])
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['ydotool', 'type', '-e', '0', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['ydotool', 'type', '-e', '0', '--', to_type])
            elif token in AUTOTYPE_TOKENS:
                cmd = ['ydotool'] + AUTOTYPE_TOKENS[token]
                call(cmd)
            else:
                dmenu_err(f"Unsupported auto-type token (ydotool): \"{token}\"")
                return
        else:
            call(['ydotool', 'type', '-e', '0', '--', token])


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
                    call(['wtype', '--', to_type])
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['wtype', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['wtype', '--', to_type])
            elif token in AUTOTYPE_TOKENS:
                cmd = ['wtype', '-k', AUTOTYPE_TOKENS[token]]
                call(cmd)
            else:
                dmenu_err(f"Unsupported auto-type token (wtype): \"{token}\"")
                return
        else:
            call(['wtype', '--', token])


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
                    _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=f"type {to_type}")
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=f"type {to_type}")
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=f"type {to_type}")
            elif token in AUTOTYPE_TOKENS:
                to_type = " ".join(AUTOTYPE_TOKENS[token])
                _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=to_type)
            else:
                dmenu_err(f"Unsupported auto-type token (dotool): \"{token}\"")
                return
        else:
            _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=f"type {token}")


def type_text(data):
    """Type the given text data

    """
    if keepmenu.CLIPBOARD is True:
        type_clipboard(data)
        return
    library = 'pynput'
    if keepmenu.CONF.has_option('database', 'type_library'):
        library = keepmenu.CONF.get('database', 'type_library')
    if library == 'xdotool':
        call(['xdotool', 'type', '--', data])
    elif library == 'ydotool':
        call(['ydotool', 'type', '-e', '0', '--', data])
    elif library == 'wtype':
        call(['wtype', '--', data])
    elif library == 'dotool':
        _ = run(['dotool'], check=True, encoding=keepmenu.ENC, input=f"type {data}")
    else:
        try:
            from pynput import keyboard
        except ModuleNotFoundError:
            return
        kbd = keyboard.Controller()
        try:
            kbd.type(data)
        except kbd.InvalidCharacterException:
            dmenu_err("Unable to type string...bad character.\n"
                      "Try setting `type_library = xdotool` in config.ini")


def type_clipboard(text):
    """Copy text to clipboard and clear clipboard after 30 seconds

    Args: text - str

    """
    text = text or ""  # Handle None type
    run(split(keepmenu.CLIPBOARD_CMD), check=True, input=text.encode(keepmenu.ENC))
    clear = Timer(30, lambda: run(split(keepmenu.CLIPBOARD_CMD), check=False, input=""))
    clear.start()
