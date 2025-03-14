"""Non-interactive CLI functionality for keepmenu

This module provides functions for running keepmenu commands without
interactive prompts, suitable for scripting and CLI-only usage.
"""

from os.path import expanduser
import keepmenu
import os
import sys
from keepmenu.keepmenu import get_database, get_entries
from keepmenu.type import type_clipboard


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


def show_password(kp_entries, search_string, use_clipboard=False, return_errors=False):
    """Show password for entries matching the search string.

    If multiple entries match, return an error.
    If only one entry matches, show its password directly.

    Args:
        kp_entries - list of KeePass entries
        search_string - string to search for
        use_clipboard - whether to copy to clipboard instead of stdout
        return_errors - if True, return error messages instead of printing to stderr

    Returns: password string, error string (if return_errors), or None
    """
    matches = search_entries(kp_entries, search_string)

    if not matches:
        error_msg = f"No entries found matching '{search_string}'"
        if return_errors:
            return f"ERROR: {error_msg}"
        print(error_msg, file=sys.stderr)
        return None

    if len(matches) > 1:
        error_lines = [f"Multiple entries found matching '{search_string}'. Please be more specific."]
        for entry in matches:
            title = entry.deref("title") or ""
            username = entry.deref("username") or ""
            path = "/".join(entry.path[:-1])
            error_lines.append(f"  - {os.path.join(path, title)} ({username})")
        if return_errors:
            return "ERROR: " + "\n".join(error_lines)
        for line in error_lines:
            print(line, file=sys.stderr)
        return None

    entry = matches[0]
    password = entry.deref("password") or ""

    if use_clipboard:
        type_clipboard(password)
        return None
    else:
        return password  # Return password instead of printing it


def run_once(db=None, **kwargs):
    """Run keepmenu once for a single operation and exit

    This requires database path to be specified and will not prompt for any user input.

    Args: kpo = existing list of entries if db is already unlocked
          database - path to database
          keyfile - path to keyfile
          clipboard - use clipboard
          show - search string to show password
          return_errors - if True, return error messages instead of printing to stderr

    Returns: password string if show option is used, otherwise None
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

        # Get entries
        db.kpo = get_entries(db, cli_mode=True)
        if db.kpo is None:
            error_msg = "Error: Could not retrieve entries from database"
            if return_errors:
                return f"ERROR: {error_msg}"
            print(error_msg, file=sys.stderr)
            return None

    search = kwargs.get("show", "")
    return show_password(db.kpo.entries, search, keepmenu.CLIPBOARD, return_errors=return_errors)
