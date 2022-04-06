# flake8: noqa
from pynput import keyboard

AUTOTYPE_TOKENS = {
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
