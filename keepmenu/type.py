"""Methods for typing entries with pynput, xdotool, ydotool, wtype

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
    elif library == 'wtype':
        type_entry_wtype(entry, tokens)
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
    "{TAB}"       : ['key', '15:1', '15:0'],
    "{ENTER}"     : ['key', '28:1', '28:0'],
    "~"           : ['key', '28:1', '28:0'],
    "{UP}"        : ['key', '103:1', '103:0'],
    "{DOWN}"      : ['key', '108:1', '108:0'],
    "{LEFT}"      : ['key', '105:1', '105:0'],
    "{RIGHT}"     : ['key', '106:1', '106:0'],
    "{INSERT}"    : ['key', '110:1', '110:0'],
    "{INS}"       : ['key', '110:1', '110:0'],
    "{DELETE}"    : ['key', '111:1', '111:0'],
    "{DEL}"       : ['key', '111:1', '111:0'],
    "{HOME}"      : ['key', '102:1', '102:0'],
    "{END}"       : ['key', '107:1', '107:0'],
    "{PGUP}"      : ['key', '104:1', '104:0'],
    "{PGDN}"      : ['key', '109:1', '109:0'],
    "{SPACE}"     : ['key', '57:1', '57:0'],
    "{BACKSPACE}" : ['key', '14:1', '14:0'],
    "{BS}"        : ['key', '14:1', '14:0'],
    "{BKSP}"      : ['key', '14:1', '14:0'],
    "{BREAK}"     : ['key', '0x19b:1', '0x19b:0'],
    "{CAPSLOCK}"  : ['key', '58:1', '58:0'],
    "{ESC}"       : ['key', '1:1', '1:0'],
    "{WIN}"       : ['key', '125:1', '125:0'],
    "{LWIN}"      : ['key', '125:1', '125:0'],
    "{RWIN}"      : ['key', '126:1', '126:0'],
    "{APPS}"      : ['key', '0x244:1', '0x244:0'],
    "{HELP}"      : ['key', '138:1', '138:0'],
    "{NUMLOCK}"   : ['key', '69:1', '69:0'],
    "{PRTSC}"     : ['key', '99:1', '99:0'],
    "{SCROLLLOCK}": ['key', '70:1', '70:0'],
    "{F1}"        : ['key', '59:1', '59:0'],
    "{F2}"        : ['key', '60:1', '60:0'],
    "{F3}"        : ['key', '61:1', '61:0'],
    "{F4}"        : ['key', '62:1', '62:0'],
    "{F5}"        : ['key', '63:1', '63:0'],
    "{F6}"        : ['key', '64:1', '64:0'],
    "{F7}"        : ['key', '65:1', '65:0'],
    "{F8}"        : ['key', '66:1', '66:0'],
    "{F9}"        : ['key', '67:1', '67:0'],
    "{F10}"       : ['key', '68:1', '68:0'],
    "{F11}"       : ['key', '87:1', '87:0'],
    "{F12}"       : ['key', '88:1', '88:0'],
    "{F13}"       : ['key', '183:1', '183:0'],
    "{F14}"       : ['key', '184:1', '184:0'],
    "{F15}"       : ['key', '185:1', '185:0'],
    "{F16}"       : ['key', '186:1', '186:0'],
    "{ADD}"       : ['key', '78:1', '78:0'],
    "{SUBTRACT}"  : ['key', '74:1', '74:0'],
    "{MULTIPLY}"  : ['key', '55:1', '55:0'],
    "{DIVIDE}"    : ['key', '98:1', '98:0'],
    "{NUMPAD0}"   : ['key', '82:1', '82:0'],
    "{NUMPAD1}"   : ['key', '79:1', '79:0'],
    "{NUMPAD2}"   : ['key', '80:1', '80:0'],
    "{NUMPAD3}"   : ['key', '81:1', '81:0'],
    "{NUMPAD4}"   : ['key', '75:1', '75:0'],
    "{NUMPAD5}"   : ['key', '76:1', '76:0'],
    "{NUMPAD6}"   : ['key', '77:1', '77:0'],
    "{NUMPAD7}"   : ['key', '71:1', '71:0'],
    "{NUMPAD8}"   : ['key', '72:1', '72:0'],
    "{NUMPAD9}"   : ['key', '73:1', '73:0'],
    "+"           : ['key', '42:1', '42:0'],
    "^"           : ['Key', '29:1', '29:0'],
    "%"           : ['key', '56:1', '56:0'],
    "@"           : ['key', '125:1', '125:0']
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

WTYPE_AUTOTYPE_TOKENS = {
    "{TAB}"       : 'Tab',
    "{ENTER}"     : 'Return',
    "~"           : 'Return',
    "{UP}"        : 'Up',
    "{DOWN}"      : 'Down',
    "{LEFT}"      : 'Left',
    "{RIGHT}"     : 'Right',
    "{INSERT}"    : 'Insert',
    "{INS}"       : 'Insert',
    "{DELETE}"    : 'Delete',
    "{DEL}"       : 'Delete',
    "{HOME}"      : 'Home',
    "{END}"       : 'End',
    "{PGUP}"      : 'Page_Up',
    "{PGDN}"      : 'Page_Down',
    "{SPACE}"     : 'Space',
    "{BACKSPACE}" : 'BackSpace',
    "{BS}"        : 'BackSpace',
    "{BKSP}"      : 'BackSpace',
    "{BREAK}"     : 'Break',
    "{CAPSLOCK}"  : 'Caps_Lock',
    "{ESC}"       : 'Escape',
    "{WIN}"       : 'Meta_L',
    "{LWIN}"      : 'Meta_L',
    "{RWIN}"      : 'Meta_R',
    # "{APPS}"      :  '',
    "{HELP}"      :  'Help',
    "{NUMLOCK}"   :  'Num_Lock',
    "{PRTSC}"     :  'Print',
    "{SCROLLLOCK}":  'Scroll_Lock',
    "{F1}"        :  'F1',
    "{F2}"        :  'F2',
    "{F3}"        :  'F3',
    "{F4}"        :  'F4',
    "{F5}"        :  'F5',
    "{F6}"        :  'F6',
    "{F7}"        :  'F7',
    "{F8}"        :  'F8',
    "{F9}"        :  'F9',
    "{F10}"       :  'F10',
    "{F11}"       :  'F11',
    "{F12}"       :  'F12',
    "{F13}"       :  'F13',
    "{F14}"       :  'F14',
    "{F15}"       :  'F15',
    "{F16}"       :  'F16',
    "{ADD}"       :  'KP_Add',
    "{SUBTRACT}"  :  'KP_Subtract',
    "{MULTIPLY}"  :  'KP_Multiply',
    "{DIVIDE}"    :  'KP_Divide',
    "{NUMPAD0}"   :  'KP_0',
    "{NUMPAD1}"   :  'KP_1',
    "{NUMPAD2}"   :  'KP_2',
    "{NUMPAD3}"   :  'KP_3',
    "{NUMPAD4}"   :  'KP_4',
    "{NUMPAD5}"   :  'KP_5',
    "{NUMPAD6}"   :  'KP_6',
    "{NUMPAD7}"   :  'KP_7',
    "{NUMPAD8}"   :  'KP_8',
    "{NUMPAD9}"   :  'KP_9',
    "+"           :  'Shift_L',
    "^"           :  'Ctrl_L',
    "%"           :  'Alt_L',
    "@"           :  'Meta_L',
}

def type_entry_wtype(entry, tokens):
    """Auto-type entry entry using wtype

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
                    call(['wtype', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['wtype', '--', to_type])
            elif token in WTYPE_AUTOTYPE_TOKENS:
                cmd = ['wtype', '-k', WTYPE_AUTOTYPE_TOKENS[token]]
                call(cmd)
            else:
                dmenu_err(f"Unsupported auto-type token (wtype): \"{token}\"")
                return
        else:
            call(['wtype', '--', token])

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
    elif library == 'wtype':
        call(['wtype', '--', data])
    else:
        kbd = keyboard.Controller()
        try:
            kbd.type(data)
        except kbd.InvalidCharacterException:
            dmenu_err("Unable to type string...bad character.\n"
                      "Try setting `type_library = xdotool` in config.ini")
