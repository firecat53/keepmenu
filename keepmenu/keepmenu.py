"""Read and copy Keepass database entries using dmenu or rofi

"""
from copy import deepcopy
from datetime import datetime, timedelta
import errno
import functools
from multiprocessing import Process
import os
from os.path import expanduser, realpath
import shlex
from subprocess import Popen, PIPE
import sys
from threading import Timer

import construct
import keepmenu
from keepmenu.edit import add_entry, edit_entry, manage_groups
from keepmenu.menu import dmenu_err, dmenu_select
from keepmenu.type import type_entry, type_text
from keepmenu.view import view_all_entries, view_entry


class DataBase():  # pylint: disable=too-few-public-methods
    """Define a database class for clearer reference to variables

        dbase - string, filename
        kfile - string, filename
        pword - string, password
        atype - string, autotype sequence
        kpo - PyKeePass object
        is_active - bool, is this the currently active database

    """
    def __init__(self, dbase=None, kfile=None, pword=None, atype=None, kpo=None):
        self.dbase = expanduser('' if dbase is None else dbase)
        self.dbase = realpath(self.dbase) if self.dbase else ''
        self.kfile = expanduser('' if kfile is None else kfile)
        self.kfile = realpath(self.kfile) if self.kfile else ''
        self.pword = pword
        self.atype = atype
        self.kpo = kpo
        self.is_active = False

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


def get_databases():
    """Read databases from config

    Returns: [DataBase obj, DataBase obj2,...]
             If not specified in the config, the value will be None
             If database name is None, an error has occurred

    """
    dargs = keepmenu.CONF.items('database')
    args_dict = dict(dargs)
    dbases = [i for i in args_dict if i.startswith('database')]
    dbs = []
    for dbase in dbases:
        dbn = args_dict[dbase]
        idx = dbase.rsplit('_', 1)[-1]
        try:
            keyfile = args_dict['keyfile_{}'.format(idx)]
        except KeyError:
            keyfile = None
        try:
            passw = args_dict['password_{}'.format(idx)]
        except KeyError:
            passw = None
        try:
            autotype = args_dict['autotype_default_{}'.format(idx)]
        except KeyError:
            autotype = None
        try:
            cmd = args_dict['password_cmd_{}'.format(idx)]
            res = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE).communicate()
            if res[1]:
                dmenu_err("Password command error: {}".format(res[1]))
                sys.exit()
            else:
                passw = res[0].decode().rstrip('\n') if res[0] else passw
        except KeyError:
            pass
        if dbn:
            dbo = DataBase(dbase=dbn, kfile=keyfile, pword=passw, atype=autotype)
            dbs.append(dbo)

    return dbs


def get_database(open_databases=None, **kwargs):
    """Read databases/keyfile/autotype from config, CLI, or ask for user input.

    Args: open_databases - list [DataBase1, DataBase2,...]
          kwargs - possibly 'database', 'keyfile'
    Returns: DataBase obj or None on error selecting database or password
             open_databases - list [DataBase1, DataBase2,...]
                (open_databases is managed in get_database but stored in
                DmenuRunner for persistence instead of using a global var)

    """
    dbs_cfg = get_databases()
    dbs_cfg_n = [i.dbase for i in dbs_cfg]
    open_databases = open_databases or {}
    clidb = DataBase(dbase=kwargs.get('database'),
                     kfile=kwargs.get('keyfile'),
                     atype=kwargs.get('autotype'))
    if not dbs_cfg and not clidb.dbase and not open_databases:
        # First run  database opening
        res = get_initial_db()
        if res is True:
            db_, open_databases = get_database()
            dbs = [db_]
        else:
            return None, open_databases
    elif clidb.dbase:
        # Prefer db and autotype passed via cli
        db_ = [i for i in open_databases.values() if i.dbase == clidb.dbase]
        if db_:
            dbs = [deepcopy(db_[0])]
            if clidb.atype:
                dbs[0].atype = clidb.atype
        else:
            dbs = [deepcopy(clidb)]
            # Use existing keyfile if available
            if not dbs[0].kfile and dbs[0].dbase in dbs_cfg_n:
                dbs[0].kfile = dbs_cfg[dbs_cfg_n.index(dbs[0].dbase)].kfile
            # Use existing password if available
            if not dbs[0].pword and dbs[0].dbase in dbs_cfg_n:
                dbs[0].pword = dbs_cfg[dbs_cfg_n.index(dbs[0].dbase)].pword
    elif clidb.atype and open_databases:
        # If only autotype is passed, use current db
        db_ = [i for i in open_databases.values() if i.is_active is True][0]
        dbs = [deepcopy(db_)]
        dbs[0].atype = clidb.atype
    elif open_databases:
        # if there are dbs already open, make a list of those + dbs from config.ini
        dbs = [deepcopy(i) for i in open_databases.values()]
        for db_ in dbs_cfg:
            if db_.dbase not in open_databases:
                dbs.append(deepcopy(db_))
    else:
        dbs = dbs_cfg
    if len(dbs) > 1:
        inp_bytes = "\n".join(i.dbase for i in dbs).encode(keepmenu.ENC)
        sel = dmenu_select(len(dbs), "Select Database", inp=inp_bytes)
        dbs = [i for i in dbs if i.dbase == sel]
        if not sel or not dbs:
            return None, open_databases
    if not dbs[0].pword:
        dbs[0].pword = get_passphrase()
        if not dbs[0].pword:
            return None, open_databases
    for db_ in open_databases.values():
        db_.is_active = False
    if dbs[0].dbase not in open_databases:
        open_databases[dbs[0].dbase] = deepcopy(dbs[0])
    if dbs[0].dbase in dbs_cfg_n:
        db_cfg_atype = dbs_cfg[dbs_cfg_n.index(dbs[0].dbase)].atype
        open_databases[dbs[0].dbase].atype = db_cfg_atype
        if not dbs[0].atype:
            dbs[0].atype = db_cfg_atype
    if clidb.atype:
        dbs[0].atype = clidb.atype
    open_databases[dbs[0].dbase].is_active = True
    return dbs[0], open_databases


def get_initial_db():
    """Ask for and set initial database name and keyfile if not entered in config file

    """
    db_name = dmenu_select(0, "Enter path to existing "
                              "Keepass database. ~/ for $HOME is ok")
    if not db_name:
        dmenu_err("No database entered. Try again.")
        return False
    keyfile_name = dmenu_select(0, "Enter path to keyfile. ~/ for $HOME is ok")
    with open(keepmenu.CONF_FILE, 'w') as conf_file:
        keepmenu.CONF.set('database', 'database_1', db_name)
        if keyfile_name:
            keepmenu.CONF.set('database', 'keyfile_1', keyfile_name)
        keepmenu.CONF.write(conf_file)
    return True


def get_entries(dbo):
    """Open keepass database and return the PyKeePass object

        Args: dbo: DataBase object
        Returns: PyKeePass object or None

    """
    from pykeepass import PyKeePass
    if dbo.dbase is None:
        return None
    try:
        kpo = PyKeePass(dbo.dbase, dbo.pword, keyfile=dbo.kfile)
    except (FileNotFoundError, construct.core.ChecksumError) as err:
        if str(err.args[0]).startswith("wrong checksum"):
            dmenu_err("Invalid Password or keyfile")
            return None
        try:
            if err.errno == errno.ENOENT:
                if not os.path.isfile(dbo.dbase):
                    dmenu_err("Database does not exist. Check path and filename.")
                elif not os.path.isfile(dbo.kfile):
                    dmenu_err("Keyfile does not exist. Check path and filename.")
        except AttributeError:
            pass
        return None
    except Exception as err:
        dmenu_err("Error: {}".format(err))
        return None
    return kpo


def get_passphrase():
    """Get a database password from dmenu or pinentry

    Returns: string

    """
    pinentry = None
    if keepmenu.CONF.has_option("dmenu", "pinentry"):
        pinentry = keepmenu.CONF.get("dmenu", "pinentry")
    if pinentry:
        password = ""
        out = Popen(pinentry,
                    stdout=PIPE,
                    stdin=PIPE).communicate(
                        input=b'setdesc Enter database password\ngetpin\n')[0]
        if out:
            res = out.decode(keepmenu.ENC).split("\n")[2]
            if res.startswith("D "):
                password = res.split("D ")[1]
    else:
        password = dmenu_select(0, "Password")
    return None or password


def get_expiring_entries(entries):
    """Return a list of expired entries (if they can expire)

    """
    expiring = []
    for entry in entries:
        if entry.expires is True and \
                entry.expiry_time.timestamp() < (datetime.now() + timedelta(3)).timestamp():
            expiring.append(entry)
    return expiring


class DmenuRunner(Process):
    """Listen for dmenu calling event and run keepmenu

    Args: server - Server object
          kpo - Keepass object
    """

    def __init__(self, server, **kwargs):
        Process.__init__(self)
        self.server = server
        self.database, self.open_databases = get_database(**kwargs)
        if self.database:
            self.database.kpo = get_entries(self.database)
        if not self.database or not self.database.kpo:
            self.server.kill_flag.set()
            sys.exit()
        self.expiring = get_expiring_entries(self.database.kpo.entries)
        self.prev_entry = None

    def _set_timer(self):
        """Set inactivity timer

        """
        self.cache_timer = Timer(keepmenu.CACHE_PERIOD_MIN * 60, self.cache_time)
        self.cache_timer.daemon = True
        self.cache_timer.start()

    def run(self):
        while True:
            self.server.start_flag.wait()
            if self.server.kill_flag.is_set():
                break
            if not self.database or not self.database.kpo:
                pass
            elif self.server.args_flag.is_set():
                dargs = self.server.get_args()
                self.menu_open_another_database(**dargs)
                self.server.args_flag.clear()
            else:
                self.dmenu_run()
            if self.server.cache_time_expired.is_set():
                self.server.kill_flag.set()
            if self.server.kill_flag.is_set():
                break
            self.server.start_flag.clear()

    def cache_time(self):
        """Kill keepmenu daemon when cache timer expires

        """
        self.server.cache_time_expired.set()
        self.server.args_flag.clear()
        if not self.server.start_flag.is_set():
            self.server.kill_flag.set()
            self.server.start_flag.set()

    def dmenu_run(self):
        """Run dmenu with the given list of Keepass Entry objects

        If 'hide_groups' is defined in config.ini, hide those from main and
        view/type all views.

        Args: self.database.kpo - Keepass object

        Note: I had to reload the kpo object after every save to prevent being
        affected by the gibberish password bug in pykeepass:
        https://github.com/pschmitt/pykeepass/issues/43

        Once this is fixed, the extra calls to self.database.kpo = get_entries... can be
        deleted

        """
        try:
            self.cache_timer.cancel()
        except AttributeError:
            pass
        self._set_timer()
        if keepmenu.CONF.has_option("database", "hide_groups"):
            hid_groups = keepmenu.CONF.get("database", "hide_groups").split("\n")
            # Validate ignored group names in config.ini
            hid_groups = [i for i in hid_groups if i in
                          [j.name for j in self.database.kpo.groups]]
        else:
            hid_groups = []

        filtered_entries = [
            i for i in self.database.kpo.entries if not
            any(j in "/".join(i.path[:-1]) for j in hid_groups)
        ]
        options = {
            'View/Type Individual entries':
                functools.partial(self.menu_view_type_individual_entries, hid_groups),
            'View previous entry': self.menu_view_previous_entry,
            'Edit expiring/expired passwords ({})'.format(len(self.expiring)):
                functools.partial(self.menu_edit_entries, self.expiring),
            'Edit entries': functools.partial(self.menu_edit_entries, self.database.kpo.entries),
            'Add entry': self.menu_add_entry,
            'Manage groups': self.menu_manage_groups,
            'Reload database': self.menu_reload_database,
            'Open another database': self.menu_open_another_database,
            'Kill Keepmenu daemon': self.menu_kill_daemon,
        }
        if self.prev_entry is None:
            del options['View previous entry']
        if len(self.expiring) == 0:
            del options['Edit expiring/expired passwords (0)']

        sel = view_all_entries(list(options), filtered_entries, self.database.dbase)
        if not sel:
            return
        if sel in options:
            func = options[sel]
            func()
        else:
            try:
                entry = filtered_entries[int(sel.split('-', 1)[0])]
            except (ValueError, TypeError):
                return
            type_entry(entry, self.database.atype)
            self.prev_entry = entry
        # Reset database autotype in between runs
        cur_db = [i for i in self.open_databases.values() if i.is_active is True][0]
        self.database.atype = cur_db.atype

    def menu_view_type_individual_entries(self, hid_groups):
        """Process menu entry - View/Type individual entries

        """
        options = []
        filtered_entries = [
            i for i in self.database.kpo.entries if not
            any(j in "/".join(i.path[:-1]) for j in hid_groups)
        ]
        sel = view_all_entries(options, filtered_entries, self.database.dbase)
        try:
            entry = filtered_entries[int(sel.split('-', 1)[0])]
        except (ValueError, TypeError):
            return
        text = view_entry(entry)
        type_text(text)
        self.prev_entry = entry

    def menu_view_previous_entry(self):
        """Process menu entry - View previous entry

        """
        assert self.prev_entry is not None
        text = view_entry(self.prev_entry)
        type_text(text)

    def menu_edit_entries(self, entries):
        """Process menu entry - Edit individual entries

        """
        options = []
        sel = view_all_entries(options, entries, self.database.dbase)
        try:
            entry = entries[int(sel.split('-', 1)[0])]
        except (ValueError, TypeError):
            return
        edit = True
        while edit is True:
            edit = edit_entry(self.database.kpo, entry)
        self.database.kpo.save()
        self.database.kpo = get_entries(self.database)
        self.prev_entry = entry

    def menu_add_entry(self):
        """Process menu entry - Add entry

        """
        entry = add_entry(self.database.kpo)
        if entry:
            self.database.kpo.save()
            self.database.kpo = get_entries(self.database)
            self.prev_entry = entry

    def menu_manage_groups(self):
        """Process menu entry - manage groups

        """
        group = manage_groups(self.database.kpo)
        if group:
            self.database.kpo.save()
            self.database.kpo = get_entries(self.database)

    def menu_reload_database(self):
        """Process menu entry - Reload database

        """
        self.database.kpo = get_entries(self.database)
        if not self.database.kpo:
            return
        self.expiring = get_expiring_entries(self.database.kpo.entries)
        self.dmenu_run()

    def menu_open_another_database(self, **kwargs):
        """Process menu entry - Open different database

        Args: kwargs - possibly 'database', 'keyfile', 'autotype'

        """
        prev_db, prev_open = self.database, deepcopy(self.open_databases)
        self.database, self.open_databases = get_database(self.open_databases, **kwargs)
        if self.database is None:
            self.database, self.open_databases = prev_db, prev_open
            return
        if not self.database.kpo:
            self.database.kpo = get_entries(self.database)
            if self.database.kpo is None:
                self.database, self.open_databases = prev_db, prev_open
                return
        self.expiring = get_expiring_entries(self.database.kpo.entries)
        self.dmenu_run()

    def menu_kill_daemon(self):
        """Process menu entry - Kill keepmenu daemon

        """
        try:
            self.server.kill_flag.set()
        except (EOFError, IOError):
            return


# vim: set et ts=4 sw=4 :
