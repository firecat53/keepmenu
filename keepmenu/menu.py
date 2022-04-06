"""Methods for calling dmenu/Rofi

"""
import shlex
from subprocess import run
import sys

import keepmenu


def dmenu_cmd(num_lines, prompt):
    """Parse config.ini for dmenu options

    Args: args - num_lines: number of lines to display
                 prompt: prompt to show
    Returns: command invocation (as a list of strings)
                ["dmenu", "-l", <num_lines>, "-p", <prompt>, "-i"]

    """
    command = ["dmenu"]
    if keepmenu.CONF.has_option('dmenu', 'dmenu_command'):
        command = shlex.split(keepmenu.CONF.get('dmenu', 'dmenu_command'))
    dmenu_command = command[0]
    dmenu_args = command[1:]
    obscure = True
    obscure_color = "#222222"
    if prompt == "Password":
        if keepmenu.CONF.has_option('dmenu_passphrase', 'obscure'):
            obscure = keepmenu.CONF.getboolean('dmenu_passphrase', 'obscure')
        if keepmenu.CONF.has_option('dmenu_passphrase', 'obscure_color'):
            obscure_color = keepmenu.CONF.get('dmenu_passphrase', 'obscure_color')
    if "rofi" in dmenu_command:
        dmenu = [dmenu_command, "-dmenu", "-p", str(prompt), "-l", str(num_lines)]
        if obscure is True and prompt == "Password":
            dmenu.append("-password")
    elif "dmenu" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and prompt == "Password":
            dmenu.extend(["-nb", obscure_color, "-nf", obscure_color])
    elif "bemenu" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and prompt == "Password":
            dmenu.append("-x")
    elif "wofi" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and prompt == "Password":
            dmenu.append("-P")
    else:
        # Catchall for some other menu programs. Maybe it'll run and not fail?
        dmenu = [dmenu_command]
    dmenu[1:1] = dmenu_args
    return dmenu


def dmenu_select(num_lines, prompt="Entries", inp=""):
    """Call dmenu and return the selected entry

    Args: num_lines - number of lines to display
          prompt - prompt to show
          inp - bytes string to pass to dmenu via STDIN

    Returns: sel - string

    """
    cmd = dmenu_cmd(num_lines, prompt)
    res = run(cmd,
              capture_output=True,
              check=False,
              encoding=keepmenu.ENC,
              env=keepmenu.ENV,
              input=inp)
    if res.stderr and "rofi" in cmd[0]:
        cmd = [cmd[0]] + ["-dmenu"] if "rofi" in cmd[0] else [""]
        run(cmd[0], check=False, input=res.stderr, env=keepmenu.ENV)
        sys.exit()
    return res.stdout.rstrip('\n') if res.stdout is not None else None


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    """
    return dmenu_select(1, prompt)
