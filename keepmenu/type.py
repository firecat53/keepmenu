"""Methods for typing entries with pynput, xdotool and ydotool

"""
# flake8: noqa
import re
from subprocess import call
import time

from pynput import keyboard
import keepmenu
from keepmenu.menu import dmenu_err
from keepmenu.totp import gen_otp


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
            cmd = lambda t=delay: time.sleep(int(t) / 1000)
            return True
        return False

    if _check_delay():  # {DELAY x}
        return cmd
    return None


def type_entry(entry, db_autotype=None):
    """Pick which library to use to type strings

    Defaults to pynput

    Args: entry - The entry to type
          db_autotype - the database specific autotype that overrides 'autotype_default'

    """
    sequence = keepmenu.SEQUENCE

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

    library = 'pynput'
    if keepmenu.CONF.has_option('database', 'type_library'):
        library = keepmenu.CONF.get('database', 'type_library')
    if library == 'xdotool':
        type_entry_xdotool(entry, tokens)
    elif library == 'ydotool':
        type_entry_ydotool(entry, tokens)
    else:
        type_entry_pynput(entry, tokens)


PLACEHOLDER_AUTOTYPE_TOKENS = {
    "{TITLE}"   : lambda e: e.deref('title'),
    "{USERNAME}": lambda e: e.deref('username'),
    "{URL}"     : lambda e: e.deref('url'),
    "{PASSWORD}": lambda e: e.deref('password'),
    "{NOTES}"   : lambda e: e.deref('notes'),
    "{TOTP}"    : lambda e: gen_otp(e.get_custom_property("otp")),
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

PYNPUT_AUTOTYPE_TOKENS = {
    "{TAB}"       : keyboard.Key.tab,
    "{ENTER}"     : keyboard.Key.enter,
    "~"           : keyboard.Key.enter,
    "{UP}"        : keyboard.Key.up,
    "{DOWN}"      : keyboard.Key.down,
    "{LEFT}"      : keyboard.Key.left,
    "{RIGHT}"     : keyboard.Key.right,
    "{INSERT}"    : keyboard.Key.insert,
    "{INS}"       : keyboard.Key.insert,
    "{DELETE}"    : keyboard.Key.delete,
    "{DEL}"       : keyboard.Key.delete,
    "{HOME}"      : keyboard.Key.home,
    "{END}"       : keyboard.Key.end,
    "{PGUP}"      : keyboard.Key.page_up,
    "{PGDN}"      : keyboard.Key.page_down,
    "{SPACE}"     : keyboard.Key.space,
    "{BACKSPACE}" : keyboard.Key.backspace,
    "{BS}"        : keyboard.Key.backspace,
    "{BKSP}"      : keyboard.Key.backspace,
    "{BREAK}"     : keyboard.Key.pause,
    "{CAPSLOCK}"  : keyboard.Key.caps_lock,
    "{ESC}"       : keyboard.Key.esc,
    "{WIN}"       : keyboard.Key.cmd,
    "{LWIN}"      : keyboard.Key.cmd_l,
    "{RWIN}"      : keyboard.Key.cmd_r,
    # "{APPS}"    : keyboard.Key.
    # "{HELP}"    : keyboard.Key.
    "{NUMLOCK}"   : keyboard.Key.num_lock,
    "{PRTSC}"     : keyboard.Key.print_screen,
    "{SCROLLLOCK}": keyboard.Key.scroll_lock,
    "{F1}"        : keyboard.Key.f1,
    "{F2}"        : keyboard.Key.f2,
    "{F3}"        : keyboard.Key.f3,
    "{F4}"        : keyboard.Key.f4,
    "{F5}"        : keyboard.Key.f5,
    "{F6}"        : keyboard.Key.f6,
    "{F7}"        : keyboard.Key.f7,
    "{F8}"        : keyboard.Key.f8,
    "{F9}"        : keyboard.Key.f9,
    "{F10}"       : keyboard.Key.f10,
    "{F11}"       : keyboard.Key.f11,
    "{F12}"       : keyboard.Key.f12,
    "{F13}"       : keyboard.Key.f13,
    "{F14}"       : keyboard.Key.f14,
    "{F15}"       : keyboard.Key.f15,
    "{F16}"       : keyboard.Key.f16,
    # "{ADD}"       : keyboard.Key.
    # "{SUBTRACT}"  : keyboard.Key.
    # "{MULTIPLY}"  : keyboard.Key.
    # "{DIVIDE}"    : keyboard.Key.
    # "{NUMPAD0}"   : keyboard.Key.
    # "{NUMPAD1}"   : keyboard.Key.
    # "{NUMPAD2}"   : keyboard.Key.
    # "{NUMPAD3}"   : keyboard.Key.
    # "{NUMPAD4}"   : keyboard.Key.
    # "{NUMPAD5}"   : keyboard.Key.
    # "{NUMPAD6}"   : keyboard.Key.
    # "{NUMPAD7}"   : keyboard.Key.
    # "{NUMPAD8}"   : keyboard.Key.
    # "{NUMPAD9}"   : keyboard.Key.
    "+"           : keyboard.Key.shift,
    "^"           : keyboard.Key.ctrl,
    "%"           : keyboard.Key.alt,
    "@"           : keyboard.Key.cmd,
}


def type_entry_pynput(entry, tokens):  # pylint: disable=too-many-branches
    """Use pynput to auto-type the selected entry

    """
    kbd = keyboard.Controller()
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
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
            elif token in PYNPUT_AUTOTYPE_TOKENS:
                to_tap = PYNPUT_AUTOTYPE_TOKENS[token]
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


XDOTOOL_AUTOTYPE_TOKENS = {
    "{TAB}"       : ['key', 'Tab'],
    "{ENTER}"     : ['key', 'Return'],
    "~"           : ['key', 'Return'],
    "{UP}"        : ['key', 'Up'],
    "{DOWN}"      : ['key', 'Down'],
    "{LEFT}"      : ['key', 'Left'],
    "{RIGHT}"     : ['key', 'Right'],
    "{INSERT}"    : ['key', 'Insert'],
    "{INS}"       : ['key', 'Insert'],
    "{DELETE}"    : ['key', 'Delete'],
    "{DEL}"       : ['key', 'Delete'],
    "{HOME}"      : ['key', 'Home'],
    "{END}"       : ['key', 'End'],
    "{PGUP}"      : ['key', 'Page_Up'],
    "{PGDN}"      : ['key', 'Page_Down'],
    "{SPACE}"     : ['type', ' '],
    "{BACKSPACE}" : ['key', 'BackSpace'],
    "{BS}"        : ['key', 'BackSpace'],
    "{BKSP}"      : ['key', 'BackSpace'],
    "{BREAK}"     : ['key', 'Break'],
    "{CAPSLOCK}"  : ['key', 'Caps_Lock'],
    "{ESC}"       : ['key', 'Escape'],
    "{WIN}"       : ['key', 'Super'],
    "{LWIN}"      : ['key', 'Super_L'],
    "{RWIN}"      : ['key', 'Super_R'],
    # "{APPS}"      : ['key', ''],
    # "{HELP}"      : ['key', ''],
    "{NUMLOCK}"   : ['key', 'Num_Lock'],
    # "{PRTSC}"     : ['key', ''],
    "{SCROLLLOCK}": ['key', 'Scroll_Lock'],
    "{F1}"        : ['key', 'F1'],
    "{F2}"        : ['key', 'F2'],
    "{F3}"        : ['key', 'F3'],
    "{F4}"        : ['key', 'F4'],
    "{F5}"        : ['key', 'F5'],
    "{F6}"        : ['key', 'F6'],
    "{F7}"        : ['key', 'F7'],
    "{F8}"        : ['key', 'F8'],
    "{F9}"        : ['key', 'F9'],
    "{F10}"       : ['key', 'F10'],
    "{F11}"       : ['key', 'F11'],
    "{F12}"       : ['key', 'F12'],
    "{F13}"       : ['key', 'F13'],
    "{F14}"       : ['key', 'F14'],
    "{F15}"       : ['key', 'F15'],
    "{F16}"       : ['key', 'F16'],
    "{ADD}"       : ['key', 'KP_Add'],
    "{SUBTRACT}"  : ['key', 'KP_Subtract'],
    "{MULTIPLY}"  : ['key', 'KP_Multiply'],
    "{DIVIDE}"    : ['key', 'KP_Divide'],
    "{NUMPAD0}"   : ['key', 'KP_0'],
    "{NUMPAD1}"   : ['key', 'KP_1'],
    "{NUMPAD2}"   : ['key', 'KP_2'],
    "{NUMPAD3}"   : ['key', 'KP_3'],
    "{NUMPAD4}"   : ['key', 'KP_4'],
    "{NUMPAD5}"   : ['key', 'KP_5'],
    "{NUMPAD6}"   : ['key', 'KP_6'],
    "{NUMPAD7}"   : ['key', 'KP_7'],
    "{NUMPAD8}"   : ['key', 'KP_8'],
    "{NUMPAD9}"   : ['key', 'KP_9'],
    "+"           : ['key', 'Shift'],
    "^"           : ['Key', 'Ctrl'],
    "%"           : ['key', 'Alt'],
    "@"           : ['key', 'Super'],
}


def type_entry_xdotool(entry, tokens):
    """Auto-type entry entry using xdotool

    """
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['xdotool', 'type', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['xdotool', 'type', '--', to_type])
            elif token in XDOTOOL_AUTOTYPE_TOKENS:
                cmd = ['xdotool'] + XDOTOOL_AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['xdotool'] + XDOTOOL_AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (xdotool): \"{token}\"")
                return
        else:
            call(['xdotool', 'type', '--', token])


YDOTOOL_AUTOTYPE_TOKENS = {
    "{TAB}"       : ['key', 'TAB'],
    "{ENTER}"     : ['key', 'ENTER'],
    "~"           : ['key', 'Return'],
    "{UP}"        : ['key', 'UP'],
    "{DOWN}"      : ['key', 'DOWN'],
    "{LEFT}"      : ['key', 'LEFT'],
    "{RIGHT}"     : ['key', 'RIGHT'],
    "{INSERT}"    : ['key', 'INSERT'],
    "{INS}"       : ['key', 'INSERT'],
    "{DELETE}"    : ['key', 'DELETE'],
    "{DEL}"       : ['key', 'DELETE'],
    "{HOME}"      : ['key', 'HOME'],
    "{END}"       : ['key', 'END'],
    "{PGUP}"      : ['key', 'PAGEUP'],
    "{PGDN}"      : ['key', 'PAGEDOWN'],
    "{SPACE}"     : ['type', ' '],
    "{BACKSPACE}" : ['key', 'BACKSPACE'],
    "{BS}"        : ['key', 'BACKSPACE'],
    "{BKSP}"      : ['key', 'BACKSPACE'],
    "{BREAK}"     : ['key', 'BREAK'],
    "{CAPSLOCK}"  : ['key', 'CAPSLOCK'],
    "{ESC}"       : ['key', 'ESC'],
    # "{WIN}"       : ['key', 'Super'],
    # "{LWIN}"      : ['key', 'Super_L'],
    # "{RWIN}"      : ['key', 'Super_R'],
    # "{APPS}"      : ['key', ''],
    # "{HELP}"      : ['key', ''],
    "{NUMLOCK}"   : ['key', 'NUMLOCK'],
    # "{PRTSC}"     : ['key', ''],
    "{SCROLLLOCK}": ['key', 'SCROLLLOCK'],
    "{F1}"        : ['key', 'F1'],
    "{F2}"        : ['key', 'F2'],
    "{F3}"        : ['key', 'F3'],
    "{F4}"        : ['key', 'F4'],
    "{F5}"        : ['key', 'F5'],
    "{F6}"        : ['key', 'F6'],
    "{F7}"        : ['key', 'F7'],
    "{F8}"        : ['key', 'F8'],
    "{F9}"        : ['key', 'F9'],
    "{F10}"       : ['key', 'F10'],
    "{F11}"       : ['key', 'F11'],
    "{F12}"       : ['key', 'F12'],
    "{F13}"       : ['key', 'F13'],
    "{F14}"       : ['key', 'F14'],
    "{F15}"       : ['key', 'F15'],
    "{F16}"       : ['key', 'F16'],
    "{ADD}"       : ['key', 'KPPLUS'],
    "{SUBTRACT}"  : ['key', 'KPMINUS'],
    "{MULTIPLY}"  : ['key', 'KPASTERISK'],
    "{DIVIDE}"    : ['key', 'KPSLASH'],
    "{NUMPAD0}"   : ['key', 'KP0'],
    "{NUMPAD1}"   : ['key', 'KP1'],
    "{NUMPAD2}"   : ['key', 'KP2'],
    "{NUMPAD3}"   : ['key', 'KP3'],
    "{NUMPAD4}"   : ['key', 'KP4'],
    "{NUMPAD5}"   : ['key', 'KP5'],
    "{NUMPAD6}"   : ['key', 'KP6'],
    "{NUMPAD7}"   : ['key', 'KP7'],
    "{NUMPAD8}"   : ['key', 'KP8'],
    "{NUMPAD9}"   : ['key', 'KP9'],
    "+"           : ['key', 'LEFTSHIFT'],
    "^"           : ['Key', 'LEFTCTRL'],
    "%"           : ['key', 'LEFTALT'],
    # "@"           : ['key', 'Super']
}


def type_entry_ydotool(entry, tokens):
    """Auto-type entry entry using ydotool

    """
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['ydotool', 'type', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['ydotool', 'type', '--', to_type])
            elif token in YDOTOOL_AUTOTYPE_TOKENS:
                cmd = ['ydotool'] + YDOTOOL_AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['ydotool'] + YDOTOOL_AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (ydotool): \"{token}\"")
                return
        else:
            call(['ydotool', 'type', '--', token])


def type_text(data):
    """Type the given text data

    """
    library = 'pynput'
    if keepmenu.CONF.has_option('database', 'type_library'):
        library = keepmenu.CONF.get('database', 'type_library')
    if library == 'xdotool':
        call(['xdotool', 'type', '--', data])
    elif library == 'ydotool':
        call(['ydotool', 'type', '--', data])
    else:
        kbd = keyboard.Controller()
        try:
            kbd.type(data)
        except kbd.InvalidCharacterException:
            dmenu_err("Unable to type string...bad character.\n"
                      "Try setting `type_library = xdotool` in config.ini")
