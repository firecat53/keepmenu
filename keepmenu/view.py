"""Methods to view database items

"""
import os.path
import webbrowser

import keepmenu
from keepmenu.menu import dmenu_select
from keepmenu.totp import gen_otp, get_otp_url, TOTP_FIELDS


def view_all_entries(options, kp_entries, dbname):
    """Generate numbered list of all Keepass entries and open with dmenu.

    Returns: dmenu selection

    """
    num_align = len(str(len(kp_entries)))
    kp_entry_pattern = str("{:>{na}} - {} - {} - {}")  # Path,username,url
    # Have to number each entry to capture duplicates correctly
    kps = str("\n").join([kp_entry_pattern.format(j,
                                                  os.path.join("/".join(i.path[:-1]),
                                                               i.deref('title') or ""),
                                                  i.deref('username'),
                                                  i.deref('url'),
                                                  na=num_align)
                         for j, i in enumerate(kp_entries)])
    if options:
        options_s = "\n".join(options) + "\n"
        entries_s = options_s + kps
    else:
        entries_s = kps

    prompt = f"Entries: {dbname}"
    if keepmenu.CONF.has_option('dmenu', 'title_path'):
        try:
            max_length = keepmenu.CONF.getboolean('dmenu', 'title_path')
        except ValueError:
            max_length = keepmenu.CONF.getint('dmenu', 'title_path')
        prompt = generate_prompt(max_length, dbname)

    return dmenu_select(min(keepmenu.MAX_LEN, len(options) + len(kp_entries)),
                        inp=entries_s,
                        prompt=prompt)


def view_entry(kp_entry):
    """Show title, username, password, url and notes for an entry.

    Returns: dmenu selection

    """
    fields = [os.path.join("/".join(kp_entry.path[:-1]), kp_entry.deref('title') or "")
              or "Title: None",
              kp_entry.deref('username') or "Username: None",
              '**********' if kp_entry.deref('password') else "Password: None",
              "TOTP: ******" if get_otp_url(kp_entry) else "TOTP: None",
              kp_entry.deref('url') or "URL: None",
              "Notes: <Enter to view>" if kp_entry.deref('notes') else "Notes: None",
              str(f"Expire time: {kp_entry.expiry_time}")
              if kp_entry.expires is True else "Expiry date: None"]

    attrs = kp_entry.custom_properties
    for attr in attrs:
        if attr not in TOTP_FIELDS:
            val = attrs.get(attr) or ""
            protected = kp_entry.is_custom_property_protected(attr) if \
                        hasattr(kp_entry, 'is_custom_property_protected') \
                        else False
            value = val or "None" if len(val.split('\n')) <= 1 and \
                                     not protected \
                                     else "<Enter to view>"
            fields.append(f'{attr}: {value}')

    sel = dmenu_select(len(fields), inp="\n".join(fields))
    if sel == "Notes: <Enter to view>":
        sel = view_notes(kp_entry.deref('notes'))
    elif sel == "Notes: None":
        sel = ""
    elif sel == '**********':
        sel = kp_entry.deref('password')
    elif sel == "TOTP: ******":
        sel = gen_otp(get_otp_url(kp_entry))
    elif sel == fields[4] and not keepmenu.CONF.getboolean("database", "type_url", fallback=False):
        if sel != "URL: None":
            webbrowser.open(sel)
        sel = ""
    else:
        for attr in attrs:
            if sel == f'{attr}: {attrs.get(attr) or ""}':
                sel = attrs.get(attr)
                break
            if sel == f'{attr}: <Enter to view>':
                sel = view_notes(attrs.get(attr) or "")

    return sel if not sel.endswith(": None") else ""


def view_notes(notes):
    """View the 'Notes' field line-by-line within dmenu.

    Returns: text of the selected line for typing

    """
    notes_l = notes.split('\n')
    sel = dmenu_select(min(keepmenu.MAX_LEN, len(notes_l)), inp=notes)
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
    if max_length is True or max_length is None:
        return f"Entries: {dbname}"
    # Truncate the path so that it is no more than max_length
    # or the length of the filename, whichever is larger
    filename = os.path.basename(dbname)
    if len(filename) >= max_length - 3:
        return f"Entries: {filename}"
    path = dbname.replace(os.path.expanduser("~"), "~")
    if len(path) <= max_length:
        return f"Entries: {path}"
    path = path[:(max_length - len(filename) - 3)]
    return f"Entries: {path}...{filename}"
