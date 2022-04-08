# Keepmenu Installation

[Configuration](configure.md) - [Usage](usage.md)

## Requirements

1. Python 3.7+.
2. [Pykeepass][1] >= 4.0.0 and [pynput][2]. Install via pip or your
   distribution's package manager, if available.
3. Dmenu, Rofi, Wofi or Bemenu.
4. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.
5. (optional) xdotool (for X) or ydotool (>=1.0.0, for Wayland), wtype (for
   Wayland). If you have a lot of Unicode characters or use a non-U.S. English
   keyboard layout, xdotool (or wtype) is necessary to handle typing those
   characters.

#### Archlinux

`$ sudo pacman -S python-pip dmenu`

#### Fedora 34

`$ sudo dnf install python3-devel dmenu`

#### Ubuntu 21.10

Ensure Universe repository is enabled.

`$ sudo apt install python3-pip suckless-tools`

## Install (recommended)

`$ pip install --user keepmenu`

Add ~/.local/bin to $PATH

### Install (virtualenv)

    $ python -m venv venv
    $ source venv/bin/activate
    $ pip install keepmenu

Link to the executable `venv/bin/keemenu` when assigning a keyboard shortcut.

### Install (virtualenv) from git

    $ git clone https://github.com/firecat53/keepmenu
    $ cd keepmenu
    $ make
    $ make run OR ./venv/bin/keepmenu
    
### Install (git)
  
    $ git clone https://github.com/firecat53/keepmenu
    $ cd keepmenu
    $ git checkout <branch> (if desired)
    $ pip install --user . OR
    $ pip install --user -e . (for editable install)

### Available in [Archlinux AUR][1]


## Wayland Notes

- Dmenu and Rofi will work under XWayland on wlroots based compositors such as Sway.
- The only combination I've found that works on Gnome/Wayland is Wofi with ydotool.
- To enable ydotool to work without sudo
    - Pick a group that one or more users
      belong to (e.g. `users`) and:

            $ echo "KERNEL==\"uinput\", GROUP=\"users\", MODE=\"0660\", \
            OPTIONS+=\"static_node=uinput\"" | sudo tee \
            /etc/udev/rules.d/80-uinput.rules > /dev/null
            # udevadm control --reload-rules && udevadm trigger
        
    - Create a systemd user service for ydotoold:

            ~/.config/systemd/user/ydotoold.service
            [Unit]
            Description=ydotoold Service

            [Service]
            ExecStart=/usr/bin/ydotoold

            [Install]
            WantedBy=default.target

    - Enable and start ydotoold.service:

            $ systemctl --user daemon-reload 
            $ systemctl --user enable --now ydotoold.service

### Wayland compatibility

|                | X   | Wayland(wlroots) & Xwayland | Pure wlroots Wayland | Gnome/Wayland(3) | Unicode Support |
|----------------|-----|-----------------------------|----------------------|------------------|-----------------|
| *Launchers*    |     |                             |                      |                  |                 |
| Dmenu          | Yes | No                          | No                   | No               |                 |
| Rofi           | Yes | Yes                         | No                   | No               |                 |
| Bemenu         | Yes | Yes                         | Yes                  | No               |                 |
| Wofi           | No  | Yes                         | Yes                  | Yes              |                 |
| *Typing Tools* |     |                             |                      |                  |                 |
| Pynput         | Yes | No                          | No                   | No               | No              |
| Xdotool        | Yes | No                          | No                   | No               | Yes             |
| Ydotool (1)    | Yes | Yes                         | Yes                  | Yes              | No (4)          |
| Wtype (2)      | No  | Yes                         | Yes                  | No               | Yes             |

(1) Ydotool has a [bug](https://github.com/ReimuNotMoe/ydotool/pull/133) currently that incorrectly types `^` as `~`.

(2) Wtype has a [bug](https://github.com/atx/wtype/issues/37) currently that
prevents it from typing into web based applications such as Firefox, Chromium,
VSCode. It does work in terminals, pinentry dialogs, LibreOffice and
Qutebrowser. 

(3) Gnome `modal` dialogs for SSH/GPG key entries are unusable with any password
manager that performs autotyping. You have to copy the password to the clipboard
before you need it and paste into the field because the dialog does not allow
you to navigate away once it's open. Copying to clipboard is not currently
possible in Keepmenu, although I intend to add support at some point.

(4) Supposedly you can change the keyboard language of the ydotool virtual
device in the Sway config to enable support for characters on that keyboard but
I have not tested that.

[1]: https://aur.archlinux.org/packages/keepmenu-git "Archlinux AUR"
[2]: https://github.com/moses-palmer/pynput "pynput"
