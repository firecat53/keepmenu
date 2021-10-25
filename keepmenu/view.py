"""Methods to view database items

"""
import os.path
import webbrowser

import keepmenu
from keepmenu.menu import dmenu_select
from keepmenu.totp import gen_otp


def view_all_entries(options, kp_entries, dbname):
    """Generate numbered list of all Keepass entries and open with dmenu.

    Returns: dmenu selection

    """
    num_align = len(str(len(kp_entries)))
    kp_entry_pattern = str("{:>{na}} - {} - {} - {}")  # Path,username,url
    # Have to number each entry to capture duplicates correctly
    kp_entries_b = str("\n").join([kp_entry_pattern.format(j,
                                       os.path.join("/".join(i.path[:-1]), i.deref('title') or ""),
                                       i.deref('username'),
                                       i.deref('url'),
                                       na=num_align)
                                   for j, i in enumerate(kp_entries)]).encode(keepmenu.ENC)
    if options:
        options_b = ("\n".join(options) + "\n").encode(keepmenu.ENC)
        entries_b = options_b + kp_entries_b
    else:
        entries_b = kp_entries_b

    prompt = "Entries: {}".format(dbname)
    if keepmenu.CONF.has_option('dmenu', 'title_path'):
        try:
            max_length = keepmenu.CONF.getboolean('dmenu', 'title_path')
        except ValueError:
            max_length = keepmenu.CONF.getint('dmenu', 'title_path')
        prompt = generate_prompt(max_length, dbname)

    return dmenu_select(min(keepmenu.MAX_LEN, len(options) + len(kp_entries)),
                        inp=entries_b,
                        prompt=prompt)


def view_entry(kp_entry):
    """Show title, username, password, url and notes for an entry.

    Returns: dmenu selection

    """
    fields = [os.path.join("/".join(kp_entry.path[:-1]), kp_entry.deref('title') or "")
              or "Title: None",
              kp_entry.deref('username') or "Username: None",
              '**********' if kp_entry.deref('password') else "Password: None",
              "TOTP: ******" if kp_entry.get_custom_property("otp") else "TOTP: None",
              kp_entry.deref('url') or "URL: None",
              "Notes: <Enter to view>" if kp_entry.deref('notes') else "Notes: None",
              str("Expire time: {}").format(kp_entry.expiry_time)
              if kp_entry.expires is True else "Expiry date: None"]

    kp_entries_b = "\n".join(fields).encode(keepmenu.ENC)
    sel = dmenu_select(len(fields), inp=kp_entries_b)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(kp_entry.deref('notes'))
    elif sel == "Notes: None":
        sel = ""
    elif sel == '**********':
        sel = kp_entry.deref('password')
    elif sel == "TOTP: ******":
        sel = gen_otp(kp_entry.get_custom_property("otp"))
    elif sel == fields[3]:
        if sel != "URL: None":
            webbrowser.open(sel)
        sel = ""
    return sel


def view_notes(notes):
    """View the 'Notes' field line-by-line within dmenu.

    Returns: text of the selected line for typing

    """
    notes_l = notes.split('\n')
    notes_b = "\n".join(notes_l).encode(keepmenu.ENC)
    sel = dmenu_select(min(keepmenu.MAX_LEN, len(notes_l)), inp=notes_b)
    return sel


def generate_prompt(max_length, dbname):
    """Generate a prompt in the format "Entries: {}", with "{}" replaced by
    the full path to the database truncated to a certain length

    max_length: an int giving the maximum length for the path, or a bool
    specifying whether to show the entire path (True) or to hide it (False)

    dbname: the full path to the database

    """
    if max_length is False or max_length == 0:
        return "Entries"
    elif max_length is True or max_length is None:
        return "Entries: {}".format(dbname)
    else:
        # Truncate the path so that it is no more than max_length
        # or the length of the filename, whichever is larger
        filename = os.path.basename(dbname)
        if len(filename) >= max_length - 3:
            return "Entries: {}".format(filename)
        else:
            path = dbname.replace(os.path.expanduser("~"), "~")
            if len(path) <= max_length:
                return "Entries: {}".format(path)
            else:
                path = path[:(max_length - len(filename) - 3)]
                return "Entries: {}...{}".format(path, filename)
