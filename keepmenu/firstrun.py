"""First run detection

Detect what terminal and launcher are actually installed, and ask when more
than one candidate is installed and there's a terminal to ask on.

Nothing here imports the rest of keepmenu, so it can run before the config is
loaded.

"""
import os
import sys
from shutil import which

# Launchers menu.dmenu_cmd knows how to pass flags to, most likely to be a
# deliberate choice first.
LAUNCHERS = ("rofi", "fuzzel", "bemenu", "wofi", "tofi", "wmenu", "yofi", "dmenu")

# Display servers each launcher can open a window on. The Wayland only ones
# can't start under X11 at all, so they're dropped there rather than ranked
# down. The X11 ones do run under Wayland through XWayland, so they stay on the
# list, just below the native ones.
LAUNCHER_SESSIONS = {
    "rofi": ("x11",),  # and Wayland natively, with the rofi-wayland fork
    "fuzzel": ("wayland",),
    "bemenu": ("x11", "wayland"),
    "wofi": ("wayland",),
    "tofi": ("wayland",),
    "wmenu": ("wayland",),
    "yofi": ("wayland",),
    "dmenu": ("x11",),
}

# edit.py runs the terminal as `<terminal> -e <editor> <file>` and waits for
# it to exit, so everything here has to take the rest of the line after a bare
# -e and stay in the foreground. foot ignores the flag for xterm compatibility
# and wezterm takes it as an alias for `start`; both still run the editor.
# gnome-terminal, xfce4-terminal and terminator are left out: their -e takes a
# single command string, and gnome-terminal returns before the editor exits.
TERMINALS = (
    "foot",
    "footclient",
    "alacritty",
    "kitty",
    "ghostty",
    "wezterm",
    "konsole",
    "urxvt",
    "st",
    "xterm",
)

# foot can't open a window under X11, and footclient needs a foot server too.
WAYLAND_ONLY_TERMINALS = ("foot", "footclient")

# Autotype backends that work on Wayland, least setup first, with what each
# needs, shown when asking. Pynput does not work on Wayland.
WAYLAND_TYPE_LIBRARIES = {
    "wtype": "no setup; wlroots compositors (sway, Hyprland...), not GNOME/KDE",
    "ydotool": "any compositor; needs ydotoold running and /dev/uinput access",
    "dotoolc": "any compositor; needs dotoold running and /dev/uinput access",
    "dotool": "any compositor; needs /dev/uinput access",
}

# Desktops whose compositors lack the virtual keyboard protocol wtype types
# through. wtype fails there, so it's never offered.
NO_VIRTUAL_KEYBOARD = ("gnome", "kde")


def say(*args, **kwargs):
    """print() to stderr, since stdout may be a pipe collecting --show output"""
    kwargs.setdefault("flush", True)
    print(*args, file=sys.stderr, **kwargs)


def is_wayland():
    """Whether this is a Wayland session

    Returns: bool

    """
    return bool(os.environ.get("WAYLAND_DISPLAY")) or \
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def has_tty():
    """Whether there is a terminal to ask the user questions on.

    Both stdin and stderr, which the questions go to: stdout may be a pipe
    collecting --show output. Usually there isn't: keepmenu is normally started from a keybinding.

    Returns: bool

    """
    try:
        return all(stream is not None and stream.isatty()
                   for stream in (sys.stdin, sys.stderr))
    except (ValueError, OSError):
        return False


def installed_launchers():
    """Supported launchers installed on this system, best guess first

    Returns: list of str

    """
    wayland = is_wayland()
    found = []
    for name in LAUNCHERS:
        sessions = LAUNCHER_SESSIONS[name]
        if not wayland and "x11" not in sessions:
            continue
        if which(name) is not None:
            found.append(name)
    if wayland:
        # Stable, so the preference order above still decides within each group
        found.sort(key=lambda name: "wayland" not in LAUNCHER_SESSIONS[name])
    return found


def installed_terminals():
    """Known terminals installed on this system, best guess first

    Returns: list of str

    """
    wayland = is_wayland()
    return [name for name in TERMINALS
            if (wayland or name not in WAYLAND_ONLY_TERMINALS)
            and which(name) is not None]


def installed_type_libraries():
    """Wayland autotype backends installed on this system, best guess first

    Returns: list of str, empty outside Wayland, where the pynput default works

    """
    if not is_wayland():
        return []
    found = [lib for lib in WAYLAND_TYPE_LIBRARIES if which(lib) is not None]
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if any(name in desktop for name in NO_VIRTUAL_KEYBOARD):
        found = [lib for lib in found if lib != "wtype"]
    return found


def detect_type_library(interactive=False):
    """Autotype backend to write into a fresh config.

    Args: interactive - bool, ask when more than one is installed

    Returns: str name, or None to leave the option out and use the pynput
             default. reload_config exits on a type_library that isn't
             installed, so only ever return one that was found.

    """
    return pick("Which autotype backend should keepmenu use?",
                installed_type_libraries(), interactive,
                notes=WAYLAND_TYPE_LIBRARIES)


def pick(prompt, options, interactive, notes=None):
    """Choose one of the detected options.

    Args: prompt - str, question to ask
          options - list of str, best guess first
          interactive - bool, ask when there's more than one candidate
          notes - dict of option: short description shown next to it

    Returns: str, or None if nothing was detected

    Raises: KeyboardInterrupt, so Ctrl-C can abandon setup

    """
    if not options:
        return None
    if len(options) == 1 or not interactive or not has_tty():
        return options[0]
    notes = notes or {}
    say(f"\n{prompt}")
    for num, option in enumerate(options, 1):
        note = f" - {notes[option]}" if option in notes else ""
        say(f"  {num}. {option}{note}")
    while True:
        # Not input(), which writes its prompt to stdout
        say(f"Choice [1-{len(options)}, enter for {options[0]}]: ", end="")
        try:
            line = sys.stdin.readline()
        except OSError:
            line = ""
        if not line:
            # EOF: nobody left to answer
            say()
            return options[0]
        sel = line.strip()
        if not sel:
            return options[0]
        if sel.isdigit() and 1 <= int(sel) <= len(options):
            return options[int(sel) - 1]
        say("Not one of the choices above.")


def detect(interactive=False):
    """Pick the launcher, terminal and autotype backend for a fresh config.

    Args: interactive - bool, ask when more than one candidate is installed and
                        there is a terminal to ask on. False on the paths that
                        can't prompt: the daemon, and reload_config.

    Returns: dict of config values, any of which is None when nothing suitable
             was found, which leaves that option out of the generated config

    """
    launchers = installed_launchers()
    terminals = installed_terminals()
    type_libraries = installed_type_libraries()
    if interactive and has_tty() and any(
            len(found) > 1 for found in (launchers, terminals, type_libraries)):
        say("Setting up keepmenu. Press enter to take the suggested answer.")
    return {
        "launcher": pick("Which launcher should keepmenu use?",
                         launchers, interactive),
        "terminal": pick("Which terminal should keepmenu open editors in?",
                         terminals, interactive),
        "type_library": detect_type_library(interactive),
    }


def no_launcher_msg(conf_file):
    """Message for a system with none of the supported launchers installed

    Args: conf_file - os.path of the config file that was written

    Returns: str

    """
    return (f"No supported launcher found. Install one of {', '.join(LAUNCHERS)}, "
            f"then set dmenu_command in {conf_file}.")

# vim: set et ts=4 sw=4 :
