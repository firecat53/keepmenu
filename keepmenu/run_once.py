"""Non-interactive CLI functionality for keepmenu

This module provides functions for running keepmenu commands without
interactive prompts, suitable for scripting and CLI-only usage.
"""

from os.path import expanduser
import keepmenu
import os
import sys
from keepmenu.keepmenu import get_database
from keepmenu.totp import get_otp_url, TOTP_FIELDS
from keepmenu.type import PLACEHOLDER_AUTOTYPE_TOKENS, type_clipboard

# Standard KeePass 2.x fields in the order used by `-f all`.
STANDARD_FIELDS = ("title", "username", "password", "url", "notes", "totp")
FIELD_ALL = "all"


def normalize_field(name):
    """Normalize a field name given on the command line.

    Accepts standard KeePass placeholder names with or without braces, in any
    case ('password', 'PASSWORD', '{PASSWORD}'), the special value 'all', and
    'S:<attr>' for a custom attribute (attribute name is case sensitive).

    Args: name - string
    Returns: normalized field name string
    Raises: ValueError on an unknown field name

    """
    field = name.strip()
    if field.startswith("{") and field.endswith("}"):
        field = field[1:-1].strip()
    if field.lower() == FIELD_ALL:
        return FIELD_ALL
    if field[:2].lower() == "s:":
        attr = field[2:]
        if not attr:
            raise ValueError("No attribute name given for 'S:'")
        return f"S:{attr}"
    if f"{{{field.upper()}}}" in PLACEHOLDER_AUTOTYPE_TOKENS:
        return field.lower()
    valid = ", ".join(STANDARD_FIELDS)
    raise ValueError(f"Unknown field '{name}'. Valid fields: {valid}, all, S:<attribute>")


def get_field(entry, field):
    """Return the value of a normalized field for an entry.

    Args: entry - KeePass entry
          field - normalized field name from normalize_field()

    Returns: string, empty if the field has no value

    """
    if field.startswith("S:"):
        return entry.get_custom_property(field[2:]) or ""
    if field in ("totp", "timeotp") and not get_otp_url(entry):
        return ""
    return PLACEHOLDER_AUTOTYPE_TOKENS[f"{{{field.upper()}}}"](entry) or ""


def list_fields(entry):
    """List the fields of an entry that have a value.

    Args: entry - KeePass entry
    Returns: list of normalized field names

    """
    fields = [i for i in STANDARD_FIELDS if i != "totp" and keepmenu.safe_deref(entry, i)]
    if get_otp_url(entry):
        fields.append("totp")
    fields.extend(f"S:{attr}" for attr in entry.custom_properties if attr not in TOTP_FIELDS)
    return fields


def search_entries(kp_entries, search_string):
    """Search for entries matching the search string in title, username, or URL.

    Args:
        kp_entries - list of KeePass entries
        search_string - string to search for

    Returns: list of matching entries
    """
    search_string_lower = search_string.lower()
    search_terms = search_string_lower.split()
    matches = []

    for entry in kp_entries:
        title = entry.deref("title") or ""
        username = entry.deref("username") or ""
        url = entry.deref("url") or ""
        path = "/".join(entry.path[:-1])
        full_path_title = f"{path}/{title}" if path else title

        title, username, url, path, full_path_title = \
            [i.lower() for i in (title, username, url, path, full_path_title)]

        if search_string_lower in full_path_title:
            matches.append(entry)
            continue

        # Check if all search terms are found in any combination of fields
        # Include full_path_title in the searchable fields for multi-term search
        if search_terms and all(
            any(
                term in field for field in [title, username, url, path, full_path_title]
            ) for term in search_terms
        ):
            matches.append(entry)

    return matches


def _error(lines, return_errors):
    """Report an error either as a string or on stderr.

    Args: lines - list of strings
          return_errors - if True, return the message instead of printing it

    Returns: error string prefixed with 'ERROR: ' or None

    """
    if return_errors:
        return "ERROR: " + "\n".join(lines)
    for line in lines:
        print(line, file=sys.stderr)
    return None


def show_fields(kp_entries, search_string, fields=None,
                use_clipboard=False, return_errors=False):
    """Show the requested fields of the entry matching the search string.

    If multiple entries match, return an error.

    Args:
        kp_entries - list of KeePass entries
        search_string - string to search for
        fields - list of field names to output, defaults to ['password']
        use_clipboard - whether to copy to clipboard instead of returning the text
        return_errors - if True, return error messages instead of printing to stderr

    Returns: the output string, an empty string if it was copied to the
             clipboard, an error string (if return_errors), or None

    """
    matches = search_entries(kp_entries, search_string)

    if not matches:
        return _error([f"No entries found matching '{search_string}'"], return_errors)

    if len(matches) > 1:
        error_lines = [f"Multiple entries found matching '{search_string}'. Please be more specific."]
        for entry in matches:
            title = entry.deref("title") or ""
            username = entry.deref("username") or ""
            path = "/".join(entry.path[:-1])
            error_lines.append(f"  - {os.path.join(path, title)} ({username})")
        return _error(error_lines, return_errors)

    entry = matches[0]

    try:
        fields = [normalize_field(i) for i in (fields or ["password"])]
    except ValueError as err:
        return _error([str(err)], return_errors)
    if FIELD_ALL in fields:
        # Labeled, since the caller can't tell which value is which.
        output = "\n".join(f"{i}: {get_field(entry, i)}" for i in list_fields(entry))
    else:
        output = "\n".join(get_field(entry, i) for i in fields)

    if use_clipboard:
        if not type_clipboard(output):
            return _error([keepmenu.clipboard_missing_msg()], return_errors)
        return ""
    return output


def run_once(db=None, **kwargs):
    """Run keepmenu once for a single operation and exit

    This requires database path to be specified and will not prompt for any user input.

    Args: kpo = existing list of entries if db is already unlocked
          database - path to database
          keyfile - path to keyfile
          clipboard - use clipboard
          show - search string to show password
          field - list of field names to output
          return_errors - if True, return error messages instead of printing to stderr

    Returns: the output string if the show option is used, otherwise None
    """
    # Ensure configuration is loaded
    cfile = kwargs.get("config")
    keepmenu.CLIPBOARD = kwargs.get("clipboard", False)
    keepmenu.reload_config(None if cfile is None else expanduser(cfile))
    return_errors = kwargs.get("return_errors", False)

    if db is None:
        db, _ = get_database(cli=True, **kwargs)
        if db is None:
            error_msg = "Error: Could not open database. Make sure the path is correct and password is in config."
            if return_errors:
                return f"ERROR: {error_msg}"
            print(error_msg, file=sys.stderr)
            return None

        # get_database() has already opened the database. Opening it again here
        # means paying for the key derivation twice on every lookup.
        if db.kpo is None:
            error_msg = "Error: Could not retrieve entries from database"
            if return_errors:
                return f"ERROR: {error_msg}"
            print(error_msg, file=sys.stderr)
            return None

    search = kwargs.get("show", "")
    return show_fields(db.kpo.entries,
                       search,
                       fields=kwargs.get("field"),
                       use_clipboard=keepmenu.CLIPBOARD,
                       return_errors=return_errors)
