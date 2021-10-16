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
    return dmenu_select(min(keepmenu.MAX_LEN, len(options) + len(kp_entries)),
                        inp=entries_b,
                        prompt="Entries: {}".format(dbname))


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
