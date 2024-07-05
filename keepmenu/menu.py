"""Launcher functions

"""
from os.path import basename
import shlex
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
                "yofi": ["-p", str(prompt), "dialog"],
                "fuzzel": ["-p", str(prompt) + " ", "-l", str(num_lines)]}
    command = shlex.split(keepmenu.CONF.get('dmenu', 'dmenu_command', fallback='dmenu'))
    command.extend(commands.get(basename(command[0]), []))
    pwprompts = ("Password", "password", "client_secret", "Verify password", "Enter Password")
    obscure = keepmenu.CONF.getboolean('dmenu_passphrase', 'obscure', fallback=True)
    if any(i == prompt for i in pwprompts) and obscure is True:
        pass_prompts = {"dmenu": dmenu_pass(basename(command[0])),
                        "wmenu": dmenu_pass(basename(command[0])),
                        "rofi": ['-password'],
                        "bemenu": ['-x', 'indicator', '*'],
                        "tofi": ["--hide-input=true", "--hidden-character=*"],
                        "wofi": ['-P'],
                        "yofi": ['--password'],
                        "fuzzel": ['--password']}
        command.extend(pass_prompts.get(basename(command[0]), []))
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
    cmd = dmenu_cmd(num_lines, prompt)
    res = run(cmd,
              capture_output=True,
              check=False,
              encoding=keepmenu.ENC,
              env=keepmenu.ENV,
              input=inp)
    return res.stdout.rstrip('\n') if res.stdout is not None else None


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    """
    return dmenu_select(1, prompt)
