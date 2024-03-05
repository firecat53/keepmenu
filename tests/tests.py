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

SECRET1 = 'ZYTYYE5FOAGW5ML7LRWUL4WTZLNJAMZS'
SECRET2 = 'PW4YAYYZVDE5RK2AOLKUATNZIKAFQLZO'


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
        self.assertTrue(KM.CONF.has_option("database", "database_1") and
                        KM.CONF.get("database", "database_1") == '')
        self.assertTrue(KM.CONF.has_option("database", "keyfile_1") and
                        KM.CONF.get("database", "keyfile_1") == '')
        self.assertTrue(KM.CONF.has_option("database", "pw_cache_period_min") and
                        KM.CONF.get("database", "pw_cache_period_min") ==
                        str(KM.CACHE_PERIOD_DEFAULT_MIN))

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
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name, pword='password'))
        kpo = KM.keepmenu.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)
        # Switch from `password_1` to `password_cmd_1`
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'password_1', '')
            KM.CONF.set('database', 'password_cmd_1', 'echo password')
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name, pword='password'))
        kpo = KM.keepmenu.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)
        with open(KM.CONF_FILE, 'w', encoding=KM.ENC) as conf_file:
            KM.CONF.set('database', 'autotype_default_1', '{TOTP}{ENTER}')
            KM.CONF.write(conf_file)
        database, _ = KM.keepmenu.get_database()
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name,
                                                         pword='password',
                                                         atype='{TOTP}{ENTER}'))

        database, _ = KM.keepmenu.get_database(database=db_name)
        self.assertTrue(database == KM.keepmenu.DataBase(dbase=db_name,
                                                         pword='password',
                                                         atype='{TOTP}{ENTER}'))
        kpo = KM.keepmenu.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)

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


if __name__ == "__main__":
    unittest.main()
