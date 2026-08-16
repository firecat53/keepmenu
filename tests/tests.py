"""Unit tests for keepmenu

"""
from multiprocessing.managers import BaseManager
import os
from shutil import copyfile, rmtree
import socket
import string
import sys
import tempfile
import unittest
from unittest import mock
from pykeepass import PyKeePass

import keepmenu as KM
from keepmenu import __main__  # noqa: F401
from keepmenu import run_once

SECRET1 = 'ZYTYYE5FOAGW5ML7LRWUL4WTZLNJAMZS'
SECRET2 = 'PW4YAYYZVDE5RK2AOLKUATNZIKAFQLZO'


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

        with self.assertRaises(SystemExit):
            KM.get_runtime_dir()


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

        with self.assertRaises(SystemExit):
            KM.__main__.get_auth()

    def test_symlinked_auth_file_refused(self):
        """Test that a symlink planted at the auth file path isn't followed

        """
        target = os.path.join(self.tmpdir, "target")
        os.symlink(target, KM.AUTH_FILE)

        with self.assertRaises(SystemExit):
            KM.__main__.get_auth()
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
        mgr.get_server()
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
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_more_entry)), "59008166")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_multi_entry)), "093610")
        with mock.patch('time.time', return_value=1270):
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_entry)), "626854")
            self.assertEqual(KM.totp.gen_otp(KM.totp.get_otp_url(kp2_more_entry)), "59008166")
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


if __name__ == "__main__":
    unittest.main()
