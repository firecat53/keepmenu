"""Unit tests for keepmenu

"""
import configparser
import contextlib
from contextlib import closing
import io
from multiprocessing.managers import BaseManager
import os
from shutil import copyfile, rmtree
import socket
import string
import sys
import tempfile
import time
import unittest
from unittest import mock
from pykeepass import PyKeePass

import keepmenu as KM
from keepmenu import __main__  # noqa: F401
from keepmenu import firstrun
from keepmenu import run_once

SECRET1 = 'ZYTYYE5FOAGW5ML7LRWUL4WTZLNJAMZS'
SECRET2 = 'PW4YAYYZVDE5RK2AOLKUATNZIKAFQLZO'


# Pin first run detection for the whole module. Without this, every
# reload_config() on a path that doesn't exist yet writes whatever launcher is
# installed on the machine running the tests, and anything that then calls
# dmenu_select opens a real window. firstrun itself is tested in TestFirstRun,
# which calls it directly rather than through reload_config.
mock.patch.object(
    KM, 'detect',
    return_value={"launcher": None, "terminal": None, "type_library": None}
).start()


class TestRuntimeDir(unittest.TestCase):
    """Test get_runtime_dir() function for auth file location

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Save original environment and tempfile cache
        self.orig_xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
        self.orig_tmpdir = os.environ.get('TMPDIR')
        self.orig_tempfile_tempdir = tempfile.tempdir

    def tearDown(self):
        rmtree(self.tmpdir)
        # Restore original environment
        if self.orig_xdg_runtime is not None:
            os.environ['XDG_RUNTIME_DIR'] = self.orig_xdg_runtime
        elif 'XDG_RUNTIME_DIR' in os.environ:
            del os.environ['XDG_RUNTIME_DIR']
        if self.orig_tmpdir is not None:
            os.environ['TMPDIR'] = self.orig_tmpdir
        elif 'TMPDIR' in os.environ:
            del os.environ['TMPDIR']
        # Restore tempfile cache
        tempfile.tempdir = self.orig_tempfile_tempdir

    def test_xdg_runtime_dir_used_when_set(self):
        """Test that $XDG_RUNTIME_DIR/keepmenu/ is used when available
        """
        xdg_runtime = os.path.join(self.tmpdir, 'runtime')
        os.makedirs(xdg_runtime, mode=0o700)
        os.environ['XDG_RUNTIME_DIR'] = xdg_runtime

        runtime_dir = KM.get_runtime_dir()

        self.assertEqual(runtime_dir, os.path.join(xdg_runtime, 'keepmenu'))
        self.assertTrue(os.path.exists(runtime_dir))
        self.assertEqual(os.stat(runtime_dir).st_mode & 0o777, 0o700)

    def test_tmpdir_fallback_when_xdg_runtime_unset(self):
        """Test fallback to $TMPDIR/keepmenu-<uid>/ when XDG_RUNTIME_DIR not set
        """
        if 'XDG_RUNTIME_DIR' in os.environ:
            del os.environ['XDG_RUNTIME_DIR']
        custom_tmpdir = os.path.join(self.tmpdir, 'tmp')
        os.makedirs(custom_tmpdir, mode=0o777)
        os.environ['TMPDIR'] = custom_tmpdir
        # Reset tempfile cache so it picks up new TMPDIR
        tempfile.tempdir = None

        runtime_dir = KM.get_runtime_dir()

        expected = os.path.join(custom_tmpdir, f'keepmenu-{os.getuid()}')
        self.assertEqual(runtime_dir, expected)
        self.assertTrue(os.path.exists(runtime_dir))
        self.assertEqual(os.stat(runtime_dir).st_mode & 0o777, 0o700)

    def test_tmpdir_fallback_when_xdg_runtime_dir_not_exists(self):
        """Test fallback when XDG_RUNTIME_DIR is set but doesn't exist
        """
        os.environ['XDG_RUNTIME_DIR'] = '/nonexistent/path'
        custom_tmpdir = os.path.join(self.tmpdir, 'tmp')
        os.makedirs(custom_tmpdir, mode=0o777)
        os.environ['TMPDIR'] = custom_tmpdir
        # Reset tempfile cache so it picks up new TMPDIR
        tempfile.tempdir = None

        runtime_dir = KM.get_runtime_dir()

        expected = os.path.join(custom_tmpdir, f'keepmenu-{os.getuid()}')
        self.assertEqual(runtime_dir, expected)

    def test_insecure_runtime_dir_refused(self):
        """Test that a pre-existing world accessible runtime dir is refused

        A local attacker can create $TMPDIR/keepmenu-<uid>/ before we do, then
        read the port and authkey we write into it.

        """
        if 'XDG_RUNTIME_DIR' in os.environ:
            del os.environ['XDG_RUNTIME_DIR']
        custom_tmpdir = os.path.join(self.tmpdir, 'tmp')
        os.makedirs(custom_tmpdir, mode=0o777)
        os.environ['TMPDIR'] = custom_tmpdir
        tempfile.tempdir = None
        os.makedirs(os.path.join(custom_tmpdir, f'keepmenu-{os.getuid()}'), mode=0o777)

        err = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(err):
            KM.get_runtime_dir()
        self.assertIn("accessible by other users", err.getvalue())


class TestServer(unittest.TestCase):
    """Test various BaseManager server functions

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        KM.AUTH_FILE = os.path.join(self.tmpdir, "keepmenu-auth")

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_auth(self):
        """Test get_auth returns port(int) and key(bytes), and when run a second
        time returns those same values from the cache file

        """
        port, key = KM.__main__.get_auth()
        self.assertIsInstance(port, int)
        if sys.version_info.major < 3:
            self.assertIsInstance(key, str)
        else:
            self.assertIsInstance(key, bytes)
        port2, key2 = KM.__main__.get_auth()
        self.assertEqual(port2, port)
        self.assertEqual(key2, key)

    def test_auth_file_is_private(self):
        """Test the auth file is created 0600 and holds a strong authkey

        """
        _, key = KM.__main__.get_auth()
        self.assertEqual(os.stat(KM.AUTH_FILE).st_mode & 0o777, 0o600)
        self.assertGreaterEqual(len(key), 32)
        self.assertIsNone(KM.check_private_path(KM.AUTH_FILE, isdir=False))

    def test_insecure_auth_file_refused(self):
        """Test that a world readable auth file is refused rather than used

        """
        with open(KM.AUTH_FILE, 'w', encoding=KM.ENC) as a_file:
            a_file.write("[DEFAULT]\nport = 1234\nauthkey = attacker\n")
        os.chmod(KM.AUTH_FILE, 0o666)

        err = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(err):
            KM.__main__.get_auth()
        self.assertIn("accessible by other users", err.getvalue())

    def test_symlinked_auth_file_refused(self):
        """Test that a symlink planted at the auth file path isn't followed

        """
        target = os.path.join(self.tmpdir, "target")
        os.symlink(target, KM.AUTH_FILE)

        err = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(err):
            KM.__main__.get_auth()
        self.assertIn("not a regular file", err.getvalue())
        self.assertFalse(os.path.exists(target))

    def test_client_without_server(self):
        """Ensure client raises an error with no server running

        """
        self.assertRaises(socket.error, KM.__main__.client, port=1, auth='abcd'.encode(KM.ENC))

    def test_server(self):
        """Ensure BaseManager server starts

        """
        server = KM.__main__.Server()
        server.start()
        self.assertTrue(server.is_alive())
        server.terminate()

    def test_client_with_server(self):
        """Ensure client() function can connect with a BaseManager server
        instance

        """
        port, key = KM.__main__.get_auth()
        mgr = BaseManager(address=('127.0.0.1', port), authkey=key)
        mgr.start()  # pylint: disable=consider-using-with
        self.assertIsInstance(KM.__main__.client(port, key), BaseManager)
        mgr.shutdown()

    def test_pipe_from_client_to_server(self):
        """Ensure client can send message to server via a pipe

        """

        server = KM.__main__.Server()
        server.start()
        conn = server._get_pipe()  # pylint: disable=protected-access
        conn.send('test')
        self.assertEqual('test', server.get_args())
        server.terminate()


class TestFunctions(unittest.TestCase):
    """Test the various Keepass functions

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        KM.CONF_FILE = os.path.join(self.tmpdir, "keepmenu-config.ini")

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_config_option(self):
        # First test default config
        KM.reload_config(os.path.join(self.tmpdir, "config.ini"))
        self.assertTrue(KM.menu.dmenu_cmd(10, "Entries") == ["dmenu", "-p", "Entries", "-l", "10"])
        # Test full config
        copyfile("tests/keepmenu-config.ini", os.path.join(self.tmpdir, "keepmenu-config.ini"))
        KM.reload_config(os.path.join(self.tmpdir, "keepmenu-config.ini"))
        self.assertTrue(KM.CONF.get("database", "database_1") == "test.kdbx")
        res = ["/usr/bin/dmenu", "-i", "-l", "10", "-fn", "Inconsolata-12",
               "-nb", "#909090", "-nf", "#999999", "-b", "-p", "Password",
               "-l", "20", "-nb", "#222222", "-nf", "#222222", ]
        self.assertTrue(KM.menu.dmenu_cmd(20, "Password") == res)

    def test_get_password_conf(self):
        """Test proper reading of password config names with spaces

        """
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.reload_config()
        self.assertTrue(KM.CONF.has_section("password_chars"))
        self.assertTrue(KM.CONF.has_option("password_chars", "punc min") and
                        KM.CONF.get("password_chars", "punc min") == "!@#$%")
        self.assertTrue(KM.CONF.has_section("password_char_presets"))
        self.assertTrue(KM.CONF.has_option("password_char_presets", "Minimal Punc") and
                        KM.CONF.get("password_char_presets", "Minimal Punc") ==
                        'upper lower digits "punc min"')

    def test_generate_password(self):
        """Test gen_passwd function

        """
        chars = {'Letters': {'upper': string.ascii_uppercase,
                             'lower': string.ascii_lowercase},
                 'Min Punc': {'min punc': '!@#$%',
                              'digits': string.digits,
                              'upper': 'ABCDE'}}
        self.assertFalse(KM.edit.gen_passwd({}))
        pword = KM.edit.gen_passwd(chars, 10)
        self.assertEqual(len(pword), 10)
        pword = set(pword)
        self.assertFalse(pword.isdisjoint(set('ABCDE')))
        self.assertFalse(pword.isdisjoint(set(string.digits)))
        self.assertFalse(pword.isdisjoint(set(string.ascii_lowercase)))
        self.assertFalse(pword.isdisjoint(set(string.ascii_uppercase)))
        self.assertFalse(pword.isdisjoint(set('!@#$%')))
        self.assertTrue(pword.isdisjoint(set('   ')))
        pword = KM.edit.gen_passwd(chars, 3)
        pword = KM.edit.gen_passwd(chars, 5)
        self.assertEqual(len(pword), 5)
        chars = {'Min Punc': {'min punc': '!@#$%',
                              'digits': string.digits,
                              'upper': 'ABCDE'}}
        pword = KM.edit.gen_passwd(chars, 50)
        self.assertEqual(len(pword), 50)
        pword = set(pword)
        self.assertFalse(pword.isdisjoint(set('ABCDE')))
        self.assertFalse(pword.isdisjoint(set(string.digits)))
        self.assertFalse(pword.isdisjoint(set('!@#$%')))
        self.assertTrue(pword.isdisjoint(set(string.ascii_lowercase)))
        self.assertTrue(pword.isdisjoint(set('   ')))

    def test_generated_password_shuffled_with_a_csprng(self):
        """The character order is part of the password, so it can't come from
        the Mersenne Twister

        """
        chars = {'Letters': {'upper': string.ascii_uppercase,
                             'lower': string.ascii_lowercase}}
        with mock.patch('random.shuffle') as mt_shuffle, \
                mock.patch.object(KM.edit, 'SystemRandom') as sysrandom:
            pword = KM.edit.gen_passwd(chars, 10)
        self.assertEqual(len(pword), 10)
        mt_shuffle.assert_not_called()
        sysrandom.return_value.shuffle.assert_called_once()

    def test_conf(self):
        """Test generating config file when none exists

        """
        KM.reload_config()
        self.assertTrue(KM.CONF.has_section("dmenu"))
        self.assertTrue(KM.CONF.has_section("dmenu_passphrase"))
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "obscure_color") and
                        KM.CONF.get("dmenu_passphrase", "obscure_color") == "#222222")
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "obscure") and
                        KM.CONF.get("dmenu_passphrase", "obscure") == "True")
        self.assertTrue(KM.CONF.has_section("database"))
        # database_1/keyfile_1 are commented out examples, not empty values
        self.assertFalse(KM.CONF.has_option("database", "database_1"))
        self.assertFalse(KM.CONF.has_option("database", "keyfile_1"))
        self.assertEqual(KM.keepmenu.get_databases(), [])
        self.assertTrue(KM.CONF.has_option("database", "pw_cache_period_min") and
                        KM.CONF.get("database", "pw_cache_period_min") ==
                        str(KM.CACHE_PERIOD_DEFAULT_MIN))
        self.assertTrue(KM.CONF.has_option("database", "autotype_default") and
                        KM.CONF.get("database", "autotype_default") == KM.SEQUENCE)

    def test_create_database(self):
        """Test database create

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        keyfile = os.path.join(self.tmpdir, "keyfile")
        with open(keyfile, 'wb') as fout:
            fout.write(os.urandom(1024))
        kpo = KM.keepmenu.create_db(db_name, keyfile, 'password')
        self.assertIsInstance(kpo, PyKeePass)
        self.assertEqual(kpo.filename, db_name)
        self.assertEqual(kpo.keyfile, keyfile)
        self.assertEqual(kpo.password, "password")

    def test_dmenu_cmd(self):
        """Test proper reading of dmenu command string from config.ini

        """
        self.tmpdir = tempfile.mkdtemp()
        KM.CONF_FILE = os.path.join(self.tmpdir, "config.ini")
        KM.reload_config()
        # First test default config
        self.assertTrue(KM.menu.dmenu_cmd(10, "Entries") == ["dmenu", "-p", "Entries", "-l", "10"])
        # Test full config
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.reload_config()
        res = ["/usr/bin/dmenu", "-i", "-l", "10", "-fn", "Inconsolata-12",
               "-nb", "#909090", "-nf", "#999999", "-b", "-p", "Password",
               "-l", "20", "-nb", "#222222", "-nf", "#222222"]
        self.assertTrue(KM.menu.dmenu_cmd(20, "Password") == res)

    def test_dmenu_pass_probes_the_launcher_once(self):
        """dmenu_pass() runs `<launcher> -h` to detect the password patch, so
        building a password prompt must not call it once per dict key

        """
        KM.CONF.set('dmenu', 'dmenu_command', 'dmenu')
        with mock.patch.object(KM.menu, 'dmenu_pass', return_value=['-P']) as dpass:
            self.assertEqual(KM.menu.dmenu_cmd(10, "Password")[-1], '-P')
        dpass.assert_called_once_with('dmenu')
        # Launchers with a native password flag never probe
        KM.CONF.set('dmenu', 'dmenu_command', 'rofi')
        with mock.patch.object(KM.menu, 'dmenu_pass') as dpass:
            self.assertIn('-password', KM.menu.dmenu_cmd(10, "Password"))
        dpass.assert_not_called()

    def test_generate_prompt(self):
        """Test properly generating prompt using various values of max_length
        (the title_path option in the config)

        """
        dbname = f"{os.path.expanduser('~')}/docs/passwords.kdbx"
        self.assertTrue(KM.view.generate_prompt(True, dbname) ==
                        f"Entries: {dbname}")
        self.assertTrue(KM.view.generate_prompt(len(dbname), dbname) ==
                        "Entries: ~/docs/passwords.kdbx")
        self.assertTrue(KM.view.generate_prompt(len("~/docs/passwords.kdbx"),
                                                dbname) ==
                        "Entries: ~/docs/passwords.kdbx")
        self.assertTrue(KM.view.generate_prompt(20, dbname) ==
                        "Entries: ~/d...passwords.kdbx")
        self.assertTrue(KM.view.generate_prompt(18, dbname) ==
                        "Entries: ~...passwords.kdbx")
        self.assertTrue(KM.view.generate_prompt(10, dbname) ==
                        "Entries: passwords.kdbx")
        self.assertTrue(KM.view.generate_prompt(0, dbname) ==
                        "Entries")
        self.assertTrue(KM.view.generate_prompt(False, dbname) ==
                        "Entries")

    def test_get_databases(self):
        """Test reading database information from config

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        db_name_2 = os.path.join(self.tmpdir, "test2.kdbx")
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.reload_config()
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', '')
            KM.CONF.set('database', 'password_cmd_1', 'echo password')

            KM.CONF.set('database', 'database_2', db_name_2)
            KM.CONF.set('database', 'autotype_default_2', '{TOTP}{ENTER}')

            KM.CONF.write(conf_file)

        databases = KM.keepmenu.get_databases()

        db1 = KM.keepmenu.DataBase(dbase=db_name, pword='password')
        db2 = KM.keepmenu.DataBase(dbase=db_name_2, atype='{TOTP}{ENTER}')
        self.assertEqual(db1.__dict__, databases[0].__dict__)
        self.assertEqual(db2.__dict__, databases[1].__dict__)

    def test_open_database(self):
        """Test database opens properly

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        database.kpo = None # Can't compare kpo objects
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name, pword='password'))
        kpo = KM.keepmenu.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)
        # Switch from `password_1` to `password_cmd_1`
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'password_1', '')
            KM.CONF.set('database', 'password_cmd_1', 'echo password')
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        database.kpo = None # Can't compare kpo objects
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name, pword='password'))
        kpo = KM.keepmenu.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'autotype_default_1', '{TOTP}{ENTER}')
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        database.kpo = None # Can't compare kpo objects
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name,
                                                         pword='password',
                                                         atype='{TOTP}{ENTER}'))

        database, _ = KM.keepmenu.get_database(database=db_name)
        self.assertIsInstance(database.kpo, PyKeePass)
        database.kpo = None # Can't compare DataBase objects with another object in them
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name,
                                                         pword='password',
                                                         atype='{TOTP}{ENTER}'))

    def test_resolve_references(self):
        """Test keepass references can be resolved to values

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        kpo = KM.keepmenu.get_entries(database)
        ref_entry = kpo.find_entries_by_title(title='.*REF.*', regex=True)[0]
        base_entry = kpo.find_entries_by_title(title='Test Title 1')[0]
        self.assertEqual(ref_entry.deref("title"), "Reference Entry Test - " + base_entry.title)
        self.assertEqual(ref_entry.deref("username"), base_entry.username)
        self.assertEqual(ref_entry.deref("password"), base_entry.password)
        self.assertEqual(ref_entry.deref("url"), base_entry.url)
        self.assertEqual(ref_entry.deref("notes"), base_entry.notes)

    def test_additional_attributes(self):
        """Test if additional attributes are correctly accessed

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.reload_config()
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', "password")
            KM.CONF.write(conf_file)

        database, _ = KM.keepmenu.get_database(database=db_name)
        kpo = KM.keepmenu.get_entries(database)
        entry = kpo.find_entries_by_title(title='Additional Attributes')[0]

        self.assertEqual(KM.type.token_command('{S:Attr 1}')(entry), "one")
        self.assertEqual(KM.type.token_command('{S:Attr 2}')(entry), "two")

    def test_expiry(self):
        """Test expiring/expired entries can be found

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        kpo = KM.keepmenu.get_entries(database)
        expiring_entries = KM.keepmenu.get_expiring_entries(kpo.entries)
        self.assertEqual(len(expiring_entries), 1)

    def test_tokenize_autotype(self):
        """Test tokenizing autotype strings
        """
        tokens = list(KM.type.tokenize_autotype("blah{SOMETHING}"))
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0], ("blah", False))
        self.assertEqual(tokens[1], ("{SOMETHING}", True))

        tokens = list(KM.type.tokenize_autotype("/abc{USERNAME}{ENTER}{TAB}{TAB} {SOMETHING}"))
        self.assertEqual(len(tokens), 7)
        self.assertEqual(tokens[0], ("/abc", False))
        self.assertEqual(tokens[1], ("{USERNAME}", True))
        self.assertEqual(tokens[4], ("{TAB}", True))
        self.assertEqual(tokens[5], (" ", False))
        self.assertEqual(tokens[6], ("{SOMETHING}", True))

        tokens = list(KM.type.tokenize_autotype("?{}}blah{{}{}}"))
        self.assertEqual(len(tokens), 5)
        self.assertEqual(tokens[0], ("?", False))
        self.assertEqual(tokens[1], ("{}}", True))
        self.assertEqual(tokens[2], ("blah", False))
        self.assertEqual(tokens[3], ("{{}", True))
        self.assertEqual(tokens[4], ("{}}", True))

        tokens = list(KM.type.tokenize_autotype("{DELAY 5}b{DELAY=50}"))
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0], ("{DELAY 5}", True))
        self.assertEqual(tokens[1], ("b", False))
        self.assertEqual(tokens[2], ("{DELAY=50}", True))

        tokens = list(KM.type.tokenize_autotype("+{DELAY 5}plus^carat~@{}}"))
        self.assertEqual(len(tokens), 8)
        self.assertEqual(tokens[0], ("+", True))
        self.assertEqual(tokens[1], ("{DELAY 5}", True))
        self.assertEqual(tokens[2], ("plus", False))
        self.assertEqual(tokens[3], ("^", True))
        self.assertEqual(tokens[4], ("carat", False))
        self.assertEqual(tokens[5], ("~", True))
        self.assertEqual(tokens[6], ("@", True))
        self.assertEqual(tokens[7], ("{}}", True))

    def test_token_command(self):
        """ test the token command
        """
        self.assertTrue(callable(KM.type.token_command('{DELAY 5}')))
        self.assertFalse(callable(KM.type.token_command('{DELAY 5 }')))
        self.assertFalse(callable(KM.type.token_command('{DELAY 5')))
        self.assertFalse(callable(KM.type.token_command('{DELAY a }')))
        self.assertFalse(callable(KM.type.token_command('{DELAY }')))
        self.assertFalse(callable(KM.type.token_command('{DELAY}')))
        self.assertFalse(callable(KM.type.token_command('DELAY 5}')))
        self.assertFalse(callable(KM.type.token_command('{DELAY a}')))

        self.assertTrue(callable(KM.type.token_command('{S:a}')))
        self.assertTrue(callable(KM.type.token_command('{S: a}')))
        self.assertTrue(callable(KM.type.token_command('{S: a }')))
        self.assertFalse(callable(KM.type.token_command('S: a}')))

    def test_hotp(self):
        """ adapted from https://github.com/susam/mintotp/blob/master/test.py
        """
        self.assertEqual(KM.totp.hotp(SECRET1, 0), '549419')
        self.assertEqual(KM.totp.hotp(SECRET2, 0), '009551')
        self.assertEqual(KM.totp.hotp(SECRET1, 0, 5, 'sha1', True), '9XFQT')
        self.assertEqual(KM.totp.hotp(SECRET2, 0, 5, 'sha1', True), 'QR5CX')
        self.assertEqual(KM.totp.hotp(SECRET1, 42), '626854')
        self.assertEqual(KM.totp.hotp(SECRET2, 42), '093610')
        self.assertEqual(KM.totp.hotp(SECRET1, 42, 5, 'sha1', True), '25256')
        self.assertEqual(KM.totp.hotp(SECRET2, 42, 5, 'sha1', True), 'RHH8D')

    def test_totp(self):
        """ adapted from https://github.com/susam/mintotp/blob/master/test.py
        """
        with mock.patch('time.time', return_value=0):
            self.assertEqual(KM.totp.totp(SECRET1), '549419')
            self.assertEqual(KM.totp.totp(SECRET2), '009551')
            self.assertEqual(KM.totp.totp(SECRET1, 30, 5, 'sha1', True), '9XFQT')
            self.assertEqual(KM.totp.totp(SECRET2, 30, 5, 'sha1', True), 'QR5CX')
        with mock.patch('time.time', return_value=10):
            self.assertEqual(KM.totp.totp(SECRET1), '549419')
            self.assertEqual(KM.totp.totp(SECRET2), '009551')
            self.assertEqual(KM.totp.totp(SECRET1, 30, 5, 'sha1', True), '9XFQT')
            self.assertEqual(KM.totp.totp(SECRET2, 30, 5, 'sha1', True), 'QR5CX')
        with mock.patch('time.time', return_value=1260):
            self.assertEqual(KM.totp.totp(SECRET1), '626854')
            self.assertEqual(KM.totp.totp(SECRET2), '093610')
            self.assertEqual(KM.totp.totp(SECRET1, 30, 5, 'sha1', True), '25256')
            self.assertEqual(KM.totp.totp(SECRET2, 30, 5, 'sha1', True), 'RHH8D')
        with mock.patch('time.time', return_value=1270):
            self.assertEqual(KM.totp.totp(SECRET1), '626854')
            self.assertEqual(KM.totp.totp(SECRET2), '093610')
            self.assertEqual(KM.totp.totp(SECRET1, 30, 5, 'sha1', True), '25256')
            self.assertEqual(KM.totp.totp(SECRET2, 30, 5, 'sha1', True), 'RHH8D')

    def test_gen_otp(self):
        """ Test OTP generation
        """
        otp_url_1 = "otpauth://totp/test:none?secret={secret}&period={period}&digits={digits}"
        otp_url_2 = "key={secret}&step={period}&size={digits}"
        for otp_url in [otp_url_1, otp_url_2]:
            with mock.patch('time.time', return_value=0):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=30,
                    digits=6
                )), '549419')
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET2,
                    period=30,
                    digits=6
                )), '009551')

            with mock.patch('time.time', return_value=1260):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=30,
                    digits=6
                )), '626854')
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET2,
                    period=30,
                    digits=6
                )), '093610')

            with mock.patch('time.time', return_value=1270):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=30,
                    digits=6
                )), '626854')
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET2,
                    period=30,
                    digits=6
                )), '093610')

        # A period other than the 30 second default has to be honoured
        for otp_url in [otp_url_1, otp_url_2]:
            with mock.patch('time.time', return_value=1260):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=60,
                    digits=6
                )), '409754')

        # keeotp's otp field empirically doesn't support steam encoding
        for otp_url in [otp_url_1]:
            with mock.patch('time.time', return_value=0):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=30,
                    digits=5
                ) + "&encoder=steam"), '9XFQT')
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET2,
                    period=30,
                    digits=5
                ) + "&encoder=steam"), 'QR5CX')

            with mock.patch('time.time', return_value=1260):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=30,
                    digits=5
                ) + "&encoder=steam"), '25256')
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET2,
                    period=30,
                    digits=5
                ) + "&encoder=steam"), 'RHH8D')

            with mock.patch('time.time', return_value=1270):
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET1,
                    period=30,
                    digits=5
                ) + "&encoder=steam"), '25256')
                self.assertEqual(KM.totp.gen_otp(otp_url.format(
                    secret=SECRET2,
                    period=30,
                    digits=5
                ) + "&encoder=steam"), 'RHH8D')

    def test_entry_otp(self):
        """Test OTP generation from kdbx entries
        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database = KM.keepmenu.DataBase(dbase=db_name, pword='password')
        kpo = KM.keepmenu.get_entries(database)
        # entry with otpsecret=SECRET1 in keepass2 fieldset
        kp2_entry = kpo.find_entries_by_title(title='keepass2 totp')[0]
        # entry with otpsecret=SECRET2, size=8, period=60 in keepass2 fieldset
        kp2_more_entry = kpo.find_entries_by_title(title='keepass2 totp - more fields')[0]
        # entry with otpsecret=SECRET1 as keepass2 fieldset and SECRET2 in otp field which comes first
        kp2_multi_entry = kpo.find_entries_by_title(title='keepass2 totp - multiple configs')[0]
        with mock.patch('time.time', return_value=0):
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_entry)), "549419")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_more_entry)), "04607023")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_multi_entry)), "009551")
        with mock.patch('time.time', return_value=1260):
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_entry)), "626854")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_more_entry)), "54549407")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_multi_entry)), "093610")
        with mock.patch('time.time', return_value=1270):
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_entry)), "626854")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_more_entry)), "54549407")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_multi_entry)), "093610")


    def test_show_password_single_match(self):
        """Test --show functionality with a single matching entry

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', 'password')
            KM.CONF.write(conf_file)
        KM.reload_config()

        # Test with exact title match
        result = run_once.run_once(database=db_name, show='like the € sign')
        self.assertEqual(result, '6MOpeaQ3A{eQB7BWVZ&-!')

        # Test with partial match using username search
        result = run_once.run_once(database=db_name, show='fred60')
        self.assertEqual(result, 'MkBHbBCozc')

    def test_show_password_multiple_matches(self):
        """Test --show functionality with multiple matching entries returns error

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', 'password')
            KM.CONF.write(conf_file)
        KM.reload_config()

        # Test with search term that matches multiple entries
        # "Test" appears in multiple entry titles
        with mock.patch('sys.stderr'):
            result = run_once.run_once(database=db_name, show='Test')
        self.assertIsNone(result)

    def test_show_password_no_match(self):
        """Test --show functionality with no matching entries

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', 'password')
            KM.CONF.write(conf_file)
        KM.reload_config()

        # Test with search term that matches nothing
        with mock.patch('sys.stderr'):
            result = run_once.run_once(database=db_name, show='nonexistent_xyz_123')
        self.assertIsNone(result)

    def test_show_password_with_path(self):
        """Test --show functionality with group path in search

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', 'password')
            KM.CONF.write(conf_file)
        KM.reload_config()

        # Test with group path to disambiguate - Scotty/Backblaze B2 is unique
        result = run_once.run_once(database=db_name, show='Scotty/Backblaze B2')
        self.assertTrue(result.startswith('hikW'))

    def test_show_password_return_errors(self):
        """Test --show functionality with return_errors=True returns error strings

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.set('database', 'password_1', 'password')
            KM.CONF.write(conf_file)
        KM.reload_config()

        # Test that return_errors=True returns error string instead of None
        result = run_once.run_once(database=db_name, show='nonexistent_xyz', return_errors=True)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith('ERROR:'))

        # Test multiple matches with return_errors
        result = run_once.run_once(database=db_name, show='Test', return_errors=True)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith('ERROR:'))


class TestCli(unittest.TestCase):
    """Test the CLI-only (--show/--field) functionality

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        KM.CONF_FILE = os.path.join(self.tmpdir, "keepmenu-config.ini")
        self.db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", self.db_name)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            conf_file.write("[database]\n"
                            f"database_1 = {self.db_name}\n"
                            "password_1 = password\n")
        KM.reload_config()
        self.kpo = PyKeePass(self.db_name, 'password')

    def tearDown(self):
        rmtree(self.tmpdir)
        KM.CLI = False

    def entry(self, title):
        """Return the single entry matching title"""
        matches = run_once.search_entries(self.kpo.entries, title)
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_minimal_config(self):
        """A hand written config without a [dmenu] section is usable

        """
        # setUp wrote a config with only a [database] section
        self.assertTrue(KM.CONF.has_section("dmenu"))
        self.assertEqual(KM.menu.dmenu_cmd(10, "Entries"),
                         ["dmenu", "-p", "Entries", "-l", "10"])

    def test_conf_dir_created(self):
        """Config file is created when its parent directories don't exist

        """
        conf_file = os.path.join(self.tmpdir, "no", "such", "dir", "config.ini")
        KM.reload_config(conf_file)
        self.assertTrue(os.path.isfile(conf_file))

    def test_conf_file_is_private(self):
        """docs/configure.md documents storing database passwords in
        config.ini, so it can't be created world readable

        """
        conf_dir = os.path.join(self.tmpdir, "fresh")
        conf_file = os.path.join(conf_dir, "config.ini")
        KM.reload_config(conf_file)
        self.assertEqual(os.stat(conf_file).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(conf_dir).st_mode & 0o777, 0o700)

    def test_cli_mode_errors_to_stderr(self):
        """dmenu_err prints to stderr instead of calling a launcher in CLI mode

        """
        KM.CLI = True
        with mock.patch('keepmenu.menu.dmenu_select') as sel, \
                mock.patch('sys.stderr') as err:
            KM.menu.dmenu_err("some error")
        sel.assert_not_called()
        err.write.assert_any_call("some error")

    def test_normalize_field(self):
        """Field names are case insensitive and braces are optional

        """
        for name in ('password', 'PASSWORD', '{password}', '{PASSWORD}', ' password '):
            self.assertEqual(run_once.normalize_field(name), 'password')
        for name in KM.run_once.STANDARD_FIELDS:
            self.assertEqual(run_once.normalize_field(name), name)
        self.assertEqual(run_once.normalize_field('all'), 'all')
        self.assertEqual(run_once.normalize_field('ALL'), 'all')
        # Attribute names keep their case
        self.assertEqual(run_once.normalize_field('S:Attr 1'), 'S:Attr 1')
        self.assertEqual(run_once.normalize_field('s:Attr 1'), 'S:Attr 1')
        self.assertEqual(run_once.normalize_field('{S:Attr 1}'), 'S:Attr 1')
        for name in ('bogus', '', 'S:', '{}'):
            self.assertRaises(ValueError, run_once.normalize_field, name)

    def test_get_field(self):
        """Each standard field and custom attributes are returned

        """
        entry = self.entry('Scotty/Backblaze B2')
        self.assertEqual(run_once.get_field(entry, 'title'), 'Backblaze B2')
        self.assertEqual(run_once.get_field(entry, 'username'), 'firecat53')
        self.assertTrue(run_once.get_field(entry, 'password').startswith('hikW'))
        # Fields with no value return an empty string, not None
        self.assertEqual(run_once.get_field(entry, 'url'), '')
        self.assertEqual(run_once.get_field(entry, 'totp'), '')
        self.assertEqual(run_once.get_field(entry, 'S:nonexistent'), '')

        entry = self.entry('Additional Attributes')
        self.assertEqual(run_once.get_field(entry, 'S:Attr 1'), 'one')
        self.assertEqual(run_once.get_field(entry, 'S:Attr 2: 1'), 'four')

        entry = self.entry('keepass2 totp - more')
        with mock.patch('time.time', return_value=0):
            self.assertEqual(run_once.get_field(entry, 'totp'), '04607023')
            self.assertEqual(run_once.get_field(entry, 'timeotp'), '04607023')

    def test_list_fields(self):
        """Only fields with a value are listed, TOTP plumbing attrs excluded

        list_fields determines what `-f all` outputs.

        """
        self.assertEqual(run_once.list_fields(self.entry('Scotty/Backblaze B2')),
                         ['title', 'username', 'password'])
        self.assertEqual(run_once.list_fields(self.entry('Additional Attributes')),
                         ['title', 'S:Attr 1', 'S:Attr 2', 'S:Attr 2: 1'])
        # 'TimeOtp-Secret-Base32' etc. are reported as 'totp', not as attributes
        self.assertEqual(run_once.list_fields(self.entry('keepass2 totp - more')),
                         ['title', 'username', 'password', 'url', 'totp'])

    def test_show_fields(self):
        """--field output ordering and 'all'

        """
        # Default is the password, matching the old --show behavior
        self.assertTrue(run_once.run_once(database=self.db_name,
                                          show='Scotty/Backblaze B2').startswith('hikW'))
        # Values are returned bare, one per line, in the requested order
        result = run_once.run_once(database=self.db_name,
                                   show='Scotty/Backblaze B2',
                                   field=['password', 'username'])
        self.assertEqual(result.split('\n')[1], 'firecat53')
        self.assertTrue(result.split('\n')[0].startswith('hikW'))
        # 'all' is labeled
        result = run_once.run_once(database=self.db_name,
                                   show='Additional Attributes',
                                   field=['all'])
        self.assertEqual(result, 'title: Additional Attributes\n'
                                 'S:Attr 1: one\n'
                                 'S:Attr 2: two\n'
                                 'S:Attr 2: 1: four')

    def test_show_fields_errors(self):
        """An unknown field name is an error

        """
        result = run_once.run_once(database=self.db_name,
                                   show='Scotty/Backblaze B2',
                                   field=['bogus'],
                                   return_errors=True)
        self.assertTrue(result.startswith('ERROR:'))
        with mock.patch('sys.stderr'):
            result = run_once.run_once(database=self.db_name,
                                       show='Scotty/Backblaze B2',
                                       field=['bogus'])
        self.assertIsNone(result)

    def test_show_fields_clipboard(self):
        """Clipboard mode returns an empty string on success, an error if no
        clipboard command is available

        """
        with mock.patch('keepmenu.run_once.type_clipboard', return_value=True) as clip:
            result = run_once.run_once(database=self.db_name,
                                       show='Scotty/Backblaze B2',
                                       field=['username'],
                                       clipboard=True,
                                       return_errors=True)
        clip.assert_called_once_with('firecat53')
        self.assertEqual(result, '')
        with mock.patch('keepmenu.run_once.type_clipboard', return_value=False):
            result = run_once.run_once(database=self.db_name,
                                       show='Scotty/Backblaze B2',
                                       clipboard=True,
                                       return_errors=True)
        self.assertTrue(result.startswith('ERROR:'))


class TestEditTotp(unittest.TestCase):
    """Test entering TOTP settings

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        KM.CONF_FILE = os.path.join(self.tmpdir, "keepmenu-config.ini")
        KM.reload_config(KM.CONF_FILE)
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        self.kpo = PyKeePass(db_name, 'password')
        self.entry = self.kpo.entries[0]
        self.entry.otp = ""

    def tearDown(self):
        rmtree(self.tmpdir)

    def edit_totp(self, selections):
        """Run edit_totp() against a canned list of launcher selections

        The entry has no TOTP secret, so the first prompt is "Secret Key?".
        """
        with mock.patch.object(KM.edit, 'dmenu_select', side_effect=selections), \
                mock.patch.object(KM.edit, 'dmenu_err') as err, \
                mock.patch.object(KM.edit, 'get_otp_url', return_value=""):
            KM.edit.edit_totp(self.entry)
        # dmenu_err pops a real launcher window that blocks until dismissed
        err.assert_not_called()

    def test_custom_code_size(self):
        """Test the code size prompt sets the code size, not the time step

        """
        self.edit_totp([SECRET1, "Use custom settings", "SHA-1", "45", "8"])

        self.assertIn("period=45", self.entry.otp)
        self.assertIn("digits=8", self.entry.otp)
        with mock.patch('time.time', return_value=1260):
            self.assertEqual(len(KM.totp.gen_otp(self.entry.otp)), 8)

    def test_cancel_settings_prompt(self):
        """Test cancelling out of the settings prompts leaves the entry alone

        """
        for selections in ([SECRET1, ""],
                           [SECRET1, "Use custom settings", ""],
                           [SECRET1, "Use custom settings", "SHA-1", ""],
                           [SECRET1, "Use custom settings", "SHA-1", "30", ""]):
            self.edit_totp(selections)
            self.assertEqual(self.entry.otp, "")

    def test_type_totp_not_offered_without_a_secret(self):
        """get_otp_url() returns '' rather than None for an entry with no
        TOTP, so "Type TOTP" used to be offered for every entry and typed
        nothing when picked

        """
        with mock.patch.object(KM.edit, 'dmenu_select', side_effect=[""]) as sel, \
                mock.patch.object(KM.edit, 'dmenu_err'), \
                mock.patch.object(KM.edit, 'get_otp_url', return_value=""), \
                mock.patch.object(KM.edit, 'type_text') as type_text:
            KM.edit.edit_totp(self.entry)
        self.assertEqual([i[0][1] for i in sel.call_args_list], ["Secret Key?"])
        type_text.assert_not_called()

    def test_type_totp_offered_with_a_secret(self):
        """An entry that does have a TOTP secret still gets the menu

        """
        url = f"otpauth://totp/Main:none?secret={SECRET1}&period=30&digits=6"
        with mock.patch.object(KM.edit, 'dmenu_select', side_effect=["Type TOTP"]), \
                mock.patch.object(KM.edit, 'dmenu_err'), \
                mock.patch.object(KM.edit, 'get_otp_url', return_value=url), \
                mock.patch.object(KM.edit, 'type_text') as type_text:
            KM.edit.edit_totp(self.entry)
        type_text.assert_called_once_with(KM.totp.gen_otp(url))


class TestInitialDb(unittest.TestCase):
    """Test the first run database prompts

    """
    def test_cancelled_create_db(self):
        """create_db() returns False when the two passphrases don't match, so
        reading kpo.keyfile blew up with an AttributeError

        """
        with mock.patch.object(KM.keepmenu, 'dmenu_select',
                               side_effect=["/nonexistent/new.kdbx", "y"]), \
                mock.patch.object(KM.keepmenu, 'create_db', return_value=False), \
                mock.patch.object(KM.keepmenu, 'dmenu_err'):
            self.assertFalse(KM.keepmenu.get_initial_db())


class TestClipboard(unittest.TestCase):
    """Test copying to and clearing the clipboard

    """
    def setUp(self):
        self.orig_cli = KM.CLI
        self.orig_cmd = KM.CLIPBOARD_CMD

    def tearDown(self):
        KM.CLI = self.orig_cli
        KM.CLIPBOARD_CMD = self.orig_cmd

    def test_clipboard_cmd_is_not_executed_to_detect_it(self):
        """Running a clipboard command to see whether it exists empties the
        clipboard as a side effect

        """
        KM.CLIPBOARD_CMD = None
        with mock.patch.object(KM, 'run') as run_mock, \
                mock.patch.object(KM.shutil, 'which', return_value='/usr/bin/clip'):
            cmd = KM.get_clipboard_cmd()
        run_mock.assert_not_called()
        self.assertIsNotNone(cmd)

    def test_clipboard_cleared_on_a_timer_in_daemon_mode(self):
        """The daemon outlives the copy, so a timer thread is enough

        """
        KM.CLI = False
        with mock.patch.object(KM.type, 'Timer') as timer, \
                mock.patch.object(KM.type, 'Popen') as popen:
            KM.type.clear_clipboard_later("xsel -b")
        popen.assert_not_called()
        timer.assert_called_once()
        self.assertEqual(timer.call_args[0][0], KM.type.CLIPBOARD_CLEAR_SEC)

    def test_clipboard_clear_is_detached_in_cli_mode(self):
        """A one-shot --show exits as soon as it has copied, which kills a
        timer thread and leaves the password in the clipboard for good

        """
        KM.CLI = True
        with mock.patch.object(KM.type, 'Timer') as timer, \
                mock.patch.object(KM.type, 'Popen') as popen:
            KM.type.clear_clipboard_later("xsel -b")
        timer.assert_not_called()
        popen.assert_called_once()
        self.assertEqual(popen.call_args[0][0][-2:], ["xsel", "-b"])
        self.assertTrue(popen.call_args[1]['start_new_session'])


class TestDotool(unittest.TestCase):
    """Test the dotool typing backend

    """
    def dotool_input(self, to_type, delay=None):
        """Return the stdin dotool would be given to type to_type"""
        with mock.patch.object(KM.type, 'run') as run_mock, \
                mock.patch.object(KM.type, '_effective_delay', return_value=delay):
            KM.type._dotool_type(to_type)  # pylint: disable=protected-access
        if not run_mock.call_args_list:
            return None
        self.assertEqual(run_mock.call_args[0][0], ['dotool'])
        return run_mock.call_args[1]['input']

    def test_single_line(self):
        """A value with no newline is one type command

        """
        self.assertEqual(self.dotool_input("hunter2"), "type hunter2")
        self.assertEqual(self.dotool_input("hunter2", delay="25"),
                         "typedelay 25\ntype hunter2")

    def test_newlines_cannot_inject_commands(self):
        """dotool reads one command per line from stdin, so a newline in a
        value must not start a new dotool command

        """
        self.assertEqual(self.dotool_input("pw\nkey super"),
                         "type pw\nkey enter\ntype key super")
        self.assertEqual(self.dotool_input("line1\r\nline2\rline3"),
                         "type line1\nkey enter\ntype line2\nkey enter\ntype line3")

    def test_blank_lines_preserved(self):
        """An empty line still presses enter, and types nothing

        """
        self.assertEqual(self.dotool_input("a\n\nb"),
                         "type a\nkey enter\nkey enter\ntype b")
        self.assertIsNone(self.dotool_input(""))


class TestLock(unittest.TestCase):
    """Test --lock stopping the daemon, which is what closes its databases

    """
    def test_lock_arg_from_client(self):
        """A --lock request sent to the daemon kills it, which is what drops
        the open databases

        """
        server = mock.Mock()
        server.kill_flag.is_set.side_effect = [False, True]
        server.args_flag.is_set.return_value = True
        server.get_args.return_value = {'lock': True}
        server.cache_time_expired.is_set.return_value = False
        # A daemon with one open database, without running DmenuRunner.__init__
        # (which opens a database and needs a launcher)
        run = KM.keepmenu.DmenuRunner.__new__(KM.keepmenu.DmenuRunner)
        dbo = KM.keepmenu.DataBase(dbase="tests/test.kdbx", pword="password")
        dbo.kpo = "pykeepass object"
        run.database = dbo
        run.open_databases = {dbo.dbase: dbo}
        run.shared_state = None
        run.server = server
        run.run()
        server.kill_flag.set.assert_called_once_with()
        # The lock must not fall through to the database selection menu
        server.get_args.assert_called_once_with()

    def test_lock_without_daemon_starts_nothing(self):
        """--lock with no daemon running has nothing to lock, and must not
        start a daemon (which would open a database instead)

        """
        with mock.patch.object(KM.__main__, 'get_auth',
                               return_value=(None, None)) as auth_mock, \
             mock.patch.object(KM.__main__, 'port_in_use', return_value=False), \
             mock.patch.object(KM.__main__, 'run') as run_mock, \
             mock.patch.object(KM.__main__, 'client') as client_mock, \
             mock.patch.object(KM.__main__, 'first_run_setup'), \
             mock.patch.object(sys, 'argv', ['keepmenu', '--lock']):
            KM.__main__.main()
        run_mock.assert_not_called()
        client_mock.assert_not_called()
        auth_mock.assert_called_once_with(create=False)


class TestAuthFile(unittest.TestCase):
    """Test which runs create the auth file

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.auth_file = os.path.join(self.tmpdir, ".keepmenu-auth")
        self.patch = mock.patch.object(KM, 'AUTH_FILE', self.auth_file)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        rmtree(self.tmpdir, ignore_errors=True)

    def test_no_auth_file_means_no_daemon(self):
        """A lookup only run doesn't create the auth file

        """
        self.assertEqual(KM.__main__.get_auth(create=False), (None, None))
        self.assertFalse(os.path.exists(self.auth_file))

    def test_lookup_finds_a_running_daemon(self):
        """A daemon writes the auth file before it starts, so a lookup only run
        still finds its port and authkey

        """
        port, authkey = KM.__main__.get_auth()
        self.assertTrue(os.path.exists(self.auth_file))
        self.assertEqual(KM.__main__.get_auth(create=False), (port, authkey))

    def test_stale_port_does_not_hang(self):
        """A daemon that dies without cleanup leaves an auth file, and its port
        can be taken by an unrelated process that never answers the manager
        handshake. Connecting to it has to give up instead of blocking.

        """
        with closing(socket.socket()) as sock:
            sock.bind(('127.0.0.1', 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            with mock.patch.object(KM.__main__, 'DAEMON_CONNECT_TIMEOUT', 1):
                start = time.monotonic()
                self.assertIsNone(KM.__main__.connect_to_daemon(port, b'authkey'))
                self.assertLess(time.monotonic() - start, 10)

    def test_port_probe_gives_up_on_a_wedged_listener(self):
        """A process that is listening but has stopped accepting leaves
        connect() retrying for minutes. The probe has to give up instead.

        """
        with closing(socket.socket()) as srv:
            srv.bind(('127.0.0.1', 0))
            srv.listen(1)
            port = srv.getsockname()[1]
            queued, full = [], False
            for _ in range(6):
                conn = socket.socket()
                conn.settimeout(0.5)
                try:
                    conn.connect(('127.0.0.1', port))
                    queued.append(conn)
                except OSError:
                    conn.close()
                    full = True
                    break
            try:
                start = time.monotonic()
                in_use = KM.__main__.port_in_use(port, timeout=1)
                self.assertLess(time.monotonic() - start, 10)
                if full:
                    # The accept queue filled up, so this is the wedged case
                    self.assertFalse(in_use)
            finally:
                for conn in queued:
                    conn.close()

    def test_stale_auth_file_is_removed(self):
        """A run that finds a stranger on the auth file's port removes the file,
        so this run and every later one start clean

        """
        with closing(socket.socket()) as sock:
            sock.bind(('127.0.0.1', 0))
            sock.listen(1)
            with open(self.auth_file, 'w', encoding=KM.ENC) as a_file:
                a_file.write("[DEFAULT]\n"
                             f"port = {sock.getsockname()[1]}\n"
                             f"authkey = {'a' * 64}\n")
            os.chmod(self.auth_file, 0o600)
            with mock.patch.object(KM.__main__, 'DAEMON_CONNECT_TIMEOUT', 1), \
                 mock.patch.object(KM.__main__, 'run') as run_mock, \
                 mock.patch.object(KM.__main__, 'first_run_setup'), \
                 mock.patch.object(sys, 'argv', ['keepmenu', '--lock']):
                KM.__main__.main()
        run_mock.assert_not_called()
        self.assertFalse(os.path.exists(self.auth_file))

    def test_daemon_run_creates_auth_file(self):
        """The runs that may start a daemon still create the auth file

        """
        port, authkey = KM.__main__.get_auth(create=True)
        self.assertTrue(os.path.exists(self.auth_file))
        self.assertIsInstance(port, int)
        self.assertIsInstance(authkey, bytes)


class TestSaveConfigOptions(unittest.TestCase):
    """Test the config writer

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.conf_file = os.path.join(self.tmpdir, "config.ini")
        KM.CONF = configparser.ConfigParser()

    def tearDown(self):
        rmtree(self.tmpdir)

    def write(self, text):
        with open(self.conf_file, 'w', encoding=KM.ENC) as fobj:
            fobj.write(text)

    def reread(self):
        conf = configparser.ConfigParser()
        conf.read(self.conf_file)
        return conf

    def test_sets_an_option(self):
        self.write("[database]\npw_cache_period_min = 360\n")
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx'})
        self.assertEqual(self.reread().get('database', 'database_1'), '/db.kdbx')

    def test_replaces_an_existing_setting(self):
        self.write("[database]\ndatabase_1 = /old.kdbx\n")
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/new.kdbx'})
        self.assertEqual(self.reread().get('database', 'database_1'), '/new.kdbx')

    def test_keeps_the_other_settings(self):
        """The file is rebuilt from CONF, so everything parsed has to come back

        """
        self.write("[dmenu]\ndmenu_command = rofi\n\n[database]\n"
                   "pw_cache_period_min = 30\n")
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx'})
        conf = self.reread()
        self.assertEqual(conf.get('dmenu', 'dmenu_command'), 'rofi')
        self.assertEqual(conf.get('database', 'pw_cache_period_min'), '30')

    def test_creates_a_missing_section(self):
        self.write("[dmenu]\ndmenu_command = rofi\n")
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx'})
        self.assertEqual(self.reread().get('database', 'database_1'), '/db.kdbx')

    def test_keeps_the_file_mode(self):
        """The config can hold database passwords, so 0600 has to survive

        """
        self.write("[database]\n")
        os.chmod(self.conf_file, 0o600)
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx'})
        self.assertEqual(os.stat(self.conf_file).st_mode & 0o777, 0o600)

    def test_updates_conf_in_memory(self):
        """The running process has to see the change without a reload"""
        self.write("[database]\n")
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx'})
        self.assertEqual(KM.CONF.get('database', 'database_1'), '/db.kdbx')

    def test_escaped_percent_survives_the_rebuild(self):
        """[password_chars] documents %% for a literal %. Rebuilding the file
        round-trips every value through ConfigParser, so a mangled escape here
        would corrupt password generation on the first database save

        """
        self.write("[database]\n\n[password_chars]\n"
                   "punctuation = !?#*@-+$%%\n")
        KM.reload_config(self.conf_file)
        before = KM.CONF.get('password_chars', 'punctuation')
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx'})
        KM.reload_config(self.conf_file)
        self.assertEqual(KM.CONF.get('password_chars', 'punctuation'), before)
        self.assertEqual(before, "!?#*@-+$%")

    def test_writes_both_options(self):
        self.write("[database]\n")
        KM.reload_config(self.conf_file)
        KM.save_config_options(self.conf_file, 'database',
                               {'database_1': '/db.kdbx', 'keyfile_1': '/db.key'})
        conf = self.reread()
        self.assertEqual(conf.get('database', 'database_1'), '/db.kdbx')
        self.assertEqual(conf.get('database', 'keyfile_1'), '/db.key')


class TestSaveDatabaseToConfig(unittest.TestCase):
    """Test that `keepmenu -d <db>` records the database it opened

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dbase = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", self.dbase)
        self.conf_file = os.path.join(self.tmpdir, "config.ini")
        self.fresh()

    def tearDown(self):
        rmtree(self.tmpdir)

    def fresh(self, database_section=""):
        with open(self.conf_file, 'w', encoding=KM.ENC) as fobj:
            fobj.write("[dmenu]\ndmenu_command = dmenu\n\n[database]\n"
                       "# database_1 = ~/passwords.kdbx\n"
                       "# keyfile_1 = ~/passwords.key\n" + database_section)
        KM.reload_config(self.conf_file)

    def saved(self):
        conf = configparser.ConfigParser()
        conf.read(self.conf_file)
        return conf.get('database', 'database_1', fallback=None)

    def test_saved_on_first_open(self):
        KM.keepmenu.get_database(database=self.dbase, password="password",
                                 config=self.conf_file)
        self.assertEqual(self.saved(), self.dbase)

    def test_keyfile_saved_alongside(self):
        db_ = KM.keepmenu.DataBase(dbase=self.dbase, kfile="/db.key")
        KM.keepmenu.save_database_to_config(db_, self.conf_file)
        conf = configparser.ConfigParser()
        conf.read(self.conf_file)
        self.assertEqual(conf.get('database', 'keyfile_1'), "/db.key")

    def test_keyfile_left_alone_when_there_isnt_one(self):
        """An empty keyfile_1 would be read back as a keyfile path of ''"""
        KM.keepmenu.get_database(database=self.dbase, password="password",
                                 config=self.conf_file)
        conf = configparser.ConfigParser()
        conf.read(self.conf_file)
        self.assertIsNone(conf.get('database', 'keyfile_1', fallback=None))

    def test_not_saved_when_config_already_has_a_database(self):
        """A curated config must not gain entries behind the user's back"""
        self.fresh("database_1 = /some/other.kdbx\n")
        KM.keepmenu.get_database(database=self.dbase, password="password",
                                 config=self.conf_file)
        self.assertEqual(self.saved(), "/some/other.kdbx")

    def test_not_saved_in_cli_mode(self):
        """--show is the scripting interface and shouldn't rewrite config"""
        KM.keepmenu.get_database(cli=True, database=self.dbase,
                                 password="password", config=self.conf_file)
        self.assertIsNone(self.saved())

    def test_not_saved_when_the_database_fails_to_open(self):
        """A bad password or path must not be written into the config"""
        with mock.patch.object(KM.keepmenu, 'dmenu_err'):
            KM.keepmenu.get_database(database=self.dbase, password="wrong",
                                     config=self.conf_file)
        self.assertIsNone(self.saved())

    def test_written_to_the_config_actually_in_use(self):
        """-c pointed get_initial_db() at the default config, not this one"""
        self.assertNotEqual(self.conf_file, KM.CONF_FILE)
        KM.keepmenu.get_database(database=self.dbase, password="password",
                                 config=self.conf_file)
        self.assertEqual(self.saved(), self.dbase)

    def test_read_only_config_skipped_quietly(self):
        """A read-only config (a Nix store symlink, say) is deliberate"""
        os.chmod(self.conf_file, 0o400)
        with mock.patch.object(KM.keepmenu, 'dmenu_err') as err:
            KM.keepmenu.get_database(database=self.dbase, password="password",
                                     config=self.conf_file)
        err.assert_not_called()
        self.assertIsNone(self.saved())

    def test_percent_in_path_saved(self):
        """configparser rejects a bare % as interpolation syntax"""
        db_ = KM.keepmenu.DataBase(dbase="/dbs/100%.kdbx")
        KM.keepmenu.save_database_to_config(db_, self.conf_file)
        self.assertEqual(self.saved(), "/dbs/100%.kdbx")
        self.assertEqual(KM.CONF.get('database', 'database_1'), "/dbs/100%.kdbx")

    def test_initial_db_saved_as_a_full_path(self):
        """A relative path must not depend on where keepmenu was started"""
        cwd = os.getcwd()
        os.chdir(self.tmpdir)
        try:
            with mock.patch.object(KM.keepmenu, 'dmenu_select',
                                   side_effect=["test.kdbx", ""]):
                self.assertTrue(KM.keepmenu.get_initial_db(self.conf_file))
        finally:
            os.chdir(cwd)
        self.assertEqual(self.saved(), os.path.realpath(self.dbase))

    def test_create_in_missing_directory_is_an_error_not_a_crash(self):
        missing = os.path.join(self.tmpdir, "nope", "new.kdbx")
        with mock.patch.object(KM.edit, 'dmenu_select', return_value=""), \
                mock.patch.object(KM.edit, 'dmenu_err') as err:
            self.assertFalse(KM.edit.create_db(missing, password="pw"))
        self.assertIn("Database not created", err.call_args.args[0])

    def test_cli_with_nothing_configured_is_an_error_not_a_crash(self):
        """dbs is empty here, and dbs[0] raised IndexError"""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            db_, _ = KM.keepmenu.get_database(cli=True, config=self.conf_file)
        self.assertIsNone(db_)
        self.assertIn("No database specified", err.getvalue())


class TestLauncherPrompts(unittest.TestCase):
    """Launcher arguments that the generated config's bare launcher names
    depend on

    """
    def select(self, launcher, stdout, *args):
        """Run dmenu_select against `launcher` with the real dmenu_cmd

        Returns: (result, argv the launcher was run with, stdin it was given)

        """
        conf = configparser.ConfigParser()
        conf.add_section('dmenu')
        conf.set('dmenu', 'dmenu_command', launcher)
        res = mock.Mock(stdout=stdout, returncode=0, stderr="")
        with mock.patch.object(KM, 'CONF', conf), \
                mock.patch.object(KM.menu, 'run', return_value=res) as run:
            result = KM.menu.dmenu_select(*args)
        return result, run.call_args.args[0], run.call_args.kwargs['input']

    def test_bare_fuzzel_gets_dmenu_mode(self):
        """Without --dmenu fuzzel is an app launcher that ignores stdin"""
        _, cmd, _ = self.select('fuzzel', "", 5, "Entries")
        self.assertEqual(cmd[:2], ['fuzzel', '--dmenu'])

    def test_yofi_dialog_comes_last(self):
        """dialog is a subcommand: yofi rejects options after it"""
        for prompt in ("Entries", "Password"):
            _, cmd, _ = self.select('yofi', "", 5, prompt)
            self.assertEqual(cmd[-1], 'dialog', prompt)
            self.assertEqual('--password' in cmd, prompt == "Password")

    def test_suggestion_gets_a_line(self):
        """rofi and fuzzel hide stdin entirely with zero lines"""
        for launcher in ('rofi', 'fuzzel'):
            _, cmd, _ = self.select(launcher, "", 0, "Prompt", "suggested")
            self.assertEqual(cmd[cmd.index('-l') + 1], '1', launcher)
        _, cmd, _ = self.select('rofi', "", 0, "Prompt")
        self.assertEqual(cmd[cmd.index('-l') + 1], '0')

    def test_wofi_free_text_keeps_prompt(self):
        """wofi hides its prompt while the input box has focus, which it
        always has when there are no rows

        """
        _, cmd, stdin = self.select('wofi', "", 0, "Enter path")
        self.assertEqual(stdin, " \n")
        self.assertIn('--exec-search', cmd)
        # Enter on the empty box selects the blank row itself
        self.assertEqual(self.select('wofi', " \n", 0, "Enter path")[0], "")
        self.assertEqual(self.select('wofi', "correct horse\n", 0, "Password")[0],
                         "correct horse")
        # Menus with rows, and other launchers, are left alone
        res, cmd, stdin = self.select('wofi', " \n", 2, "Pick", "a\n \nb")
        self.assertEqual((res, stdin), (" ", "a\n \nb"))
        self.assertNotIn('--exec-search', cmd)
        _, cmd, stdin = self.select('rofi', "", 0, "Enter path")
        self.assertEqual(stdin, "")
        self.assertNotIn('--exec-search', cmd)


class TestFirstRun(unittest.TestCase):
    """Test launcher/terminal/type_library detection for a fresh config

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.env = dict(os.environ)
        os.environ.pop('WAYLAND_DISPLAY', None)
        os.environ.pop('XDG_SESSION_TYPE', None)
        os.environ.pop('XDG_CURRENT_DESKTOP', None)

    def tearDown(self):
        rmtree(self.tmpdir)
        os.environ.clear()
        os.environ.update(self.env)

    @staticmethod
    def installed(*names):
        """which() that reports only `names` as installed"""
        return lambda name: f"/usr/bin/{name}" if name in names else None

    def test_x11_drops_wayland_only_launchers(self):
        """Wayland only launchers can't open a window under X11 at all

        """
        with mock.patch.object(firstrun, 'which',
                               self.installed('fuzzel', 'wofi', 'rofi', 'dmenu')):
            self.assertEqual(firstrun.installed_launchers(), ['rofi', 'dmenu'])

    def test_wayland_ranks_native_launchers_first(self):
        """X11 launchers still work through XWayland, they just rank lower

        """
        os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
        with mock.patch.object(firstrun, 'which',
                               self.installed('dmenu', 'rofi', 'wofi', 'fuzzel')):
            self.assertEqual(firstrun.installed_launchers(),
                             ['fuzzel', 'wofi', 'rofi', 'dmenu'])

    def test_preference_order_within_a_group(self):
        """dmenu is last: it's as often a dependency as it is a choice

        """
        with mock.patch.object(firstrun, 'which',
                               self.installed('dmenu', 'bemenu', 'rofi')):
            self.assertEqual(firstrun.installed_launchers(),
                             ['rofi', 'bemenu', 'dmenu'])

    def test_no_launcher_installed(self):
        with mock.patch.object(firstrun, 'which', self.installed()):
            self.assertEqual(firstrun.installed_launchers(), [])
            self.assertIsNone(firstrun.pick("?", [], interactive=False))

    def test_type_library_only_set_on_wayland(self):
        """pynput, the default, types nothing at all on Wayland

        """
        with mock.patch.object(firstrun, 'which', self.installed('wtype', 'ydotool')):
            self.assertIsNone(firstrun.detect_type_library())
            os.environ['XDG_SESSION_TYPE'] = 'wayland'
            self.assertEqual(firstrun.detect_type_library(), 'wtype')

    def test_type_library_none_when_nothing_installed(self):
        """reload_config exits on a type_library that isn't installed, so a
        Wayland session with no backend must leave the option out

        """
        os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
        with mock.patch.object(firstrun, 'which', self.installed('dmenu')):
            self.assertIsNone(firstrun.detect_type_library())

    def test_type_library_no_wtype_without_virtual_keyboard(self):
        """GNOME and KDE lack the protocol wtype types through

        """
        os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
        with mock.patch.object(firstrun, 'which',
                               self.installed('wtype', 'ydotool', 'dotool')):
            for desktop in ('GNOME', 'ubuntu:GNOME', 'KDE'):
                os.environ['XDG_CURRENT_DESKTOP'] = desktop
                self.assertEqual(firstrun.installed_type_libraries(),
                                 ['ydotool', 'dotool'], desktop)
            os.environ['XDG_CURRENT_DESKTOP'] = 'sway'
            self.assertEqual(firstrun.installed_type_libraries(),
                             ['wtype', 'ydotool', 'dotool'])

    def test_type_library_asks_with_requirements(self):
        """Each backend is listed with what it needs to work, and it's asked
        even when launcher and terminal are unambiguous

        """
        os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
        out = io.StringIO()
        with mock.patch.object(firstrun, 'which',
                               self.installed('fuzzel', 'foot', 'wtype', 'ydotool')), \
                mock.patch.object(firstrun, 'has_tty', return_value=True), \
                mock.patch.object(firstrun.sys, 'stdin', io.StringIO('2\n')), \
                contextlib.redirect_stderr(out):
            choices = firstrun.detect(interactive=True)
        self.assertEqual(choices, {'launcher': 'fuzzel', 'terminal': 'foot',
                                   'type_library': 'ydotool'})
        self.assertIn('Setting up keepmenu', out.getvalue())
        for lib in ('wtype', 'ydotool'):
            self.assertIn(f"{lib} - {firstrun.WAYLAND_TYPE_LIBRARIES[lib]}",
                          out.getvalue())

    def test_pick_takes_the_first_without_a_tty(self):
        """The usual case: keepmenu started from a keybinding

        """
        with mock.patch.object(firstrun, 'has_tty', return_value=False):
            self.assertEqual(
                firstrun.pick("?", ['rofi', 'dmenu'], interactive=True), 'rofi')

    def test_pick_asks_when_interactive(self):
        with mock.patch.object(firstrun, 'has_tty', return_value=True), \
                mock.patch.object(firstrun.sys, 'stdin', io.StringIO('2\n')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                firstrun.pick("?", ['rofi', 'dmenu'], interactive=True), 'dmenu')

    def test_pick_empty_answer_takes_the_default(self):
        with mock.patch.object(firstrun, 'has_tty', return_value=True), \
                mock.patch.object(firstrun.sys, 'stdin', io.StringIO('\n')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                firstrun.pick("?", ['rofi', 'dmenu'], interactive=True), 'rofi')

    def test_pick_questions_stay_off_stdout(self):
        """stdout may be `pw=$(keepmenu --show x)` collecting the secret

        """
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(firstrun, 'has_tty', return_value=True), \
                mock.patch.object(firstrun.sys, 'stdin', io.StringIO('2\n')), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            firstrun.pick("?", ['rofi', 'dmenu'], interactive=True)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("Choice [1-2", err.getvalue())

    def test_pick_eof_takes_the_default(self):
        with mock.patch.object(firstrun, 'has_tty', return_value=True), \
                mock.patch.object(firstrun.sys, 'stdin', io.StringIO('')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                firstrun.pick("?", ['rofi', 'dmenu'], interactive=True), 'rofi')

    def test_has_tty_needs_stderr(self):
        """The questions go to stderr, so there's nobody to ask without it

        """
        tty = mock.Mock(isatty=mock.Mock(return_value=True))
        pipe = mock.Mock(isatty=mock.Mock(return_value=False))
        with mock.patch.object(firstrun.sys, 'stdin', tty), \
                mock.patch.object(firstrun.sys, 'stderr', pipe):
            self.assertFalse(firstrun.has_tty())
        with mock.patch.object(firstrun.sys, 'stdin', tty), \
                mock.patch.object(firstrun.sys, 'stderr', tty):
            self.assertTrue(firstrun.has_tty())

    def test_first_run_setup_ctrl_c_writes_nothing(self):
        conf_file = os.path.join(self.tmpdir, "config.ini")
        with mock.patch.object(__main__, 'detect', side_effect=KeyboardInterrupt), \
                contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            __main__.first_run_setup(conf_file)
        self.assertFalse(os.path.exists(conf_file))

    def test_x11_drops_wayland_only_terminals(self):
        with mock.patch.object(firstrun, 'which',
                               self.installed('foot', 'footclient', 'xterm')):
            self.assertEqual(firstrun.installed_terminals(), ['xterm'])
            os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
            self.assertEqual(firstrun.installed_terminals(),
                             ['foot', 'footclient', 'xterm'])

    def test_single_string_e_terminals_never_offered(self):
        """Their -e takes one command string, not `-e editor file`"""
        for name in ('gnome-terminal', 'xfce4-terminal', 'terminator'):
            self.assertNotIn(name, firstrun.TERMINALS)

    def test_generated_config_is_valid_and_private(self):
        """A config written from detected values has to parse, and hold 0600

        """
        conf_file = os.path.join(self.tmpdir, "sub", "config.ini")
        KM.write_config(conf_file, launcher='fuzzel', terminal='foot',
                        type_library='wtype')
        self.assertEqual(os.stat(conf_file).st_mode & 0o777, 0o600)
        conf = configparser.ConfigParser()
        conf.read(conf_file)
        self.assertEqual(conf.get('dmenu', 'dmenu_command'), 'fuzzel')
        self.assertEqual(conf.get('database', 'terminal'), 'foot')
        self.assertEqual(conf.get('database', 'type_library'), 'wtype')

    def test_generated_config_omits_undetected_options(self):
        """An empty terminal/type_library would override the code defaults

        """
        conf_file = os.path.join(self.tmpdir, "config.ini")
        KM.write_config(conf_file, launcher=None, terminal=None,
                        type_library=None)
        conf = configparser.ConfigParser()
        conf.read(conf_file)
        self.assertEqual(conf.get('dmenu', 'dmenu_command'), 'dmenu')
        self.assertFalse(conf.has_option('database', 'terminal'))
        self.assertFalse(conf.has_option('database', 'type_library'))

    def test_first_run_setup_leaves_an_existing_config_alone(self):
        conf_file = os.path.join(self.tmpdir, "config.ini")
        with open(conf_file, 'w', encoding=KM.ENC) as fobj:
            fobj.write("[dmenu]\ndmenu_command = wofi\n")
        __main__.first_run_setup(conf_file)
        with open(conf_file, encoding=KM.ENC) as fobj:
            self.assertEqual(fobj.read(), "[dmenu]\ndmenu_command = wofi\n")


if __name__ == "__main__":
    unittest.main()
