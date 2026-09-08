"""Launcher functions

"""
from os.path import basename
import shlex
import sys
from subprocess import run

import keepmenu


def dmenu_cmd(num_lines, prompt):
    """Parse config.ini for dmenu options

    Args: args - num_lines: number of lines to display
                 prompt: prompt to show
    Returns: command invocation (as a list of strings) for
                ["dmenu", "-l", "<num_lines>", "-p", "<prompt>", "-i", ...]

    """
    commands = {"bemenu": ["-p", str(prompt), "-l", str(num_lines)],
                "dmenu": ["-p", str(prompt), "-l", str(num_lines)],
                "wmenu": ["-p", str(prompt), "-l", str(num_lines)],
                "rofi": ["-dmenu", "-p", str(prompt), "-l", str(num_lines)],
                "tofi": ["--require-match=false",
                         f"--prompt-text={str(prompt)}: ",
                         f"--num-results={str(num_lines)}"],
                "wofi": ["--dmenu", "-p", str(prompt), "-L", str(num_lines + 1)],
                "yofi": ["-p", str(prompt)],
                "fuzzel": ["--dmenu", "-p", str(prompt) + " ", "-l", str(num_lines)]}
    command = shlex.split(keepmenu.CONF.get('dmenu', 'dmenu_command', fallback='dmenu'))
    launcher = basename(command[0])
    command.extend(commands.get(launcher, []))
    pwprompts = ("Password", "password", "client_secret", "Verify password", "Enter Password")
    obscure = keepmenu.CONF.getboolean('dmenu_passphrase', 'obscure', fallback=True)
    if any(i == prompt for i in pwprompts) and obscure is True:
        pass_prompts = {"rofi": ['-password'],
                        "bemenu": ['-x', 'indicator', '*'],
                        "tofi": ["--hide-input=true", "--hidden-character=*"],
                        "wofi": ['-P'],
                        "yofi": ['--password'],
                        "fuzzel": ['--password']}
        # dmenu_pass runs the launcher to check for the password patch, so
        # only call it for the launcher actually in use.
        if launcher in ('dmenu', 'wmenu'):
            command.extend(dmenu_pass(launcher))
        else:
            command.extend(pass_prompts.get(launcher, []))
    if launcher == "yofi":
        # A subcommand, so it goes after every option, --password included
        command.append("dialog")
    return command


def dmenu_pass(command):
    """Check if dmenu passphrase patch is applied and return the correct command
    line arg list for wmenu or dmenu

    Args: command - string
    Returns: list or None

    """
    if command not in ('dmenu', 'wmenu'):
        return None
    try:
        # Check for dmenu password patch
        dm_patch = b'P' in run([command, "-h"],
                               capture_output=True,
                               check=False).stderr
    except FileNotFoundError:
        dm_patch = False
    color = keepmenu.CONF.get('dmenu_passphrase', 'obscure_color', fallback="#222222")
    dargs = { "dmenu":  ["-nb", color, "-nf", color],
              "wmenu":  ["-n", color, "-N", color] }
    return ["-P"] if dm_patch else dargs[command]


def dmenu_select(num_lines, prompt="Entries", inp=""):
    """Call dmenu and return the selected entry

    Args: num_lines - number of lines to display
          prompt - prompt to show
          inp - bytes string to pass to dmenu via STDIN

    Returns: sel - string

    """
    # With no lines, rofi and fuzzel show only the input box, hiding a
    # suggested value.
    if inp and num_lines < 1:
        num_lines = 1
    cmd = dmenu_cmd(num_lines, prompt)
    # wofi shows the prompt as GTK placeholder text, which disappears whenever
    # the input box has focus - and it always does when there's no list. A
    # blank row keeps focus on the list, and --exec-search makes enter return
    # what was typed even when it matches that row.
    wofi_filler = basename(cmd[0]) == "wofi" and not inp
    if wofi_filler:
        cmd.append("--exec-search")
        inp = " \n"
    try:
        res = run(cmd,
                  capture_output=True,
                  check=False,
                  encoding=keepmenu.ENC,
                  env=keepmenu.ENV,
                  input=inp)
    except FileNotFoundError:
        print(f"dmenu command not found: {cmd[0]}", file=sys.stderr)
        sys.exit(1)
    if res.returncode != 0 and res.stderr:
        print(f"dmenu command error: {res.stderr.strip()}", file=sys.stderr)
        # Don't exit on display errors (expected in headless environments)
        if "display" not in res.stderr.lower():
            sys.exit(1)
    if res.stdout is None:
        return None
    sel = res.stdout.rstrip('\n')
    # Enter on an empty wofi input box selects the blank row
    return "" if wofi_filler and sel == " " else sel


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    In CLI mode, print to stderr instead. A launcher isn't necessarily installed
    and there's a terminal to print to.

    """
    if keepmenu.CLI is True:
        print(prompt, file=sys.stderr)
        return None
    return dmenu_select(1, prompt)
