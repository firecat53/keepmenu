"""Unit tests for keepmenu

"""
import importlib
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

KM = importlib.machinery.SourceFileLoader('*', 'keepmenu').load_module()

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
        port, key = KM.get_auth()
        self.assertIsInstance(port, int)
        if sys.version_info.major < 3:
            self.assertIsInstance(key, str)
        else:
            self.assertIsInstance(key, bytes)
        port2, key2 = KM.get_auth()
        self.assertEqual(port2, port)
        self.assertEqual(key2, key)

    def test_client_without_server(self):
        """Ensure client raises an error with no server running

        """
        self.assertRaises(socket.error, KM.client)

    def test_server(self):
        """Ensure BaseManager server starts

        """
        server = KM.Server()
        server.start()
        self.assertTrue(server.is_alive())
        server.terminate()

    def test_client_with_server(self):
        """Ensure client() function can connect with a BaseManager server
        instance

        """
        port, key = KM.get_auth()
        mgr = BaseManager(address=('127.0.0.1', port), authkey=key)
        mgr.get_server()
        mgr.start()
        self.assertIsInstance(KM.client(), BaseManager)
        mgr.shutdown()


class TestFunctions(unittest.TestCase):
    """Test the various Keepass functions

    """
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        KM.CONF_FILE = os.path.join(self.tmpdir, "keepmenu-config.ini")

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_get_password_conf(self):
        """Test proper reading of password config names with spaces

        """
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.process_config()
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
        self.assertFalse(KM.gen_passwd({}))
        pword = KM.gen_passwd(chars, 10)
        self.assertEqual(len(pword), 10)
        pword = set(pword)
        self.assertFalse(pword.isdisjoint(set('ABCDE')))
        self.assertFalse(pword.isdisjoint(set(string.digits)))
        self.assertFalse(pword.isdisjoint(set(string.ascii_lowercase)))
        self.assertFalse(pword.isdisjoint(set(string.ascii_uppercase)))
        self.assertFalse(pword.isdisjoint(set('!@#$%')))
        self.assertTrue(pword.isdisjoint(set('   ')))
        pword = KM.gen_passwd(chars, 3)
        pword = KM.gen_passwd(chars, 5)
        self.assertEqual(len(pword), 5)
        chars = {'Min Punc': {'min punc': '!@#$%',
                              'digits': string.digits,
                              'upper': 'ABCDE'}}
        pword = KM.gen_passwd(chars, 50)
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
        KM.process_config()
        self.assertTrue(KM.CONF.has_section("dmenu"))
        self.assertTrue(KM.CONF.has_section("dmenu_passphrase"))
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "obscure_color") and
                        KM.CONF.get("dmenu_passphrase", "obscure_color") == "#222222")
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "obscure") and
                        KM.CONF.get("dmenu_passphrase", "obscure") == "True")
        self.assertTrue(KM.CONF.has_section("database"))
        self.assertTrue(KM.CONF.has_option("database", "database_1"))
        self.assertTrue(KM.CONF.has_option("database", "keyfile_1"))
        self.assertTrue(KM.CONF.has_option("database", "pw_cache_period_min") and
                        KM.CONF.get("database", "pw_cache_period_min") ==
                        str(KM.CACHE_PERIOD_DEFAULT_MIN))

    def test_dmenu_cmd(self):
        """Test proper reading of dmenu command string from config.ini

        """
        # First test default config
        KM.process_config()
        self.assertTrue(KM.dmenu_cmd(10, "Entries") ==
                        ["dmenu", "-p", "Entries"])
        # Test full config
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.process_config()
        res = ["/usr/bin/dmenu", "-i", "-l", "10", "-fn", "Inconsolata-12",
               "-nb", "#909090", "-nf", "#999999", "-b",
               "-p", "Password", "-nb", "#222222", "-nf", "#222222"]
        self.assertTrue(KM.dmenu_cmd(20, "Password") == res)

    def test_open_database(self):
        """Test database opens properly

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w') as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database = KM.get_database()
        self.assertTrue(database == (db_name, '', 'password', None))
        kpo = KM.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)
        # Switch from `password_1` to `password_cmd_1`
        with open(KM.CONF_FILE, 'w') as conf_file:
            KM.CONF.set('database', 'password_1', '')
            KM.CONF.set('database', 'password_cmd_1', 'echo password')
            KM.CONF.write(conf_file)
        database = KM.get_database()
        self.assertTrue(database == (db_name, '', 'password', None))
        kpo = KM.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)
        with open(KM.CONF_FILE, 'w') as conf_file:
            KM.CONF.set('database', 'autotype_default_1', '{TOTP}{ENTER}')
            KM.CONF.write(conf_file)
        database = KM.get_database()
        self.assertTrue(database == (db_name, '', 'password', '{TOTP}{ENTER}'))
        kpo = KM.get_entries(database)
        self.assertIsInstance(kpo, PyKeePass)


    def test_resolve_references(self):
        """Test keepass references can be resolved to values

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w') as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database = KM.get_database()
        kpo = KM.get_entries(database)
        ref_entry = kpo.find_entries_by_title(title='.*REF.*', regex=True)[0]
        base_entry = kpo.find_entries_by_title(title='Test Title 1')[0]
        self.assertEqual(ref_entry.deref("title"), "Reference Entry Test - " + base_entry.title)
        self.assertEqual(ref_entry.deref("username"), base_entry.username)
        self.assertEqual(ref_entry.deref("password"), base_entry.password)
        self.assertEqual(ref_entry.deref("url"), base_entry.url)
        self.assertEqual(ref_entry.deref("notes"), base_entry.notes)

    def test_expiry(self):
        """Test expiring/expired entries can be found

        """
        db_name = os.path.join(self.tmpdir, "test.kdbx")
        copyfile("tests/test.kdbx", db_name)
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        with open(KM.CONF_FILE, 'w') as conf_file:
            KM.CONF.set('database', 'database_1', db_name)
            KM.CONF.write(conf_file)
        database = KM.get_database()
        kpo = KM.get_entries(database)
        expiring_entries = KM.get_expiring_entries(kpo.entries)
        self.assertEqual(len(expiring_entries), 1)

    def test_tokenize_autotype(self):
        """Test tokenizing autotype strings
        """
        tokens = [t for t in KM.tokenize_autotype("blah{SOMETHING}")]
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0], ("blah", False))
        self.assertEqual(tokens[1], ("{SOMETHING}", True))

        tokens = [t for t in KM.tokenize_autotype("/abc{USERNAME}{ENTER}{TAB}{TAB} {SOMETHING}")]
        self.assertEqual(len(tokens), 7)
        self.assertEqual(tokens[0], ("/abc", False))
        self.assertEqual(tokens[1], ("{USERNAME}", True))
        self.assertEqual(tokens[4], ("{TAB}", True))
        self.assertEqual(tokens[5], (" ", False))
        self.assertEqual(tokens[6], ("{SOMETHING}", True))

        tokens = [t for t in KM.tokenize_autotype("?{}}blah{{}{}}")]
        self.assertEqual(len(tokens), 5)
        self.assertEqual(tokens[0], ("?", False))
        self.assertEqual(tokens[1], ("{}}", True))
        self.assertEqual(tokens[2], ("blah", False))
        self.assertEqual(tokens[3], ("{{}", True))
        self.assertEqual(tokens[4], ("{}}", True))

        tokens = [t for t in KM.tokenize_autotype("{DELAY 5}b{DELAY=50}")]
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0], ("{DELAY 5}", True))
        self.assertEqual(tokens[1], ("b", False))
        self.assertEqual(tokens[2], ("{DELAY=50}", True))

        tokens = [t for t in KM.tokenize_autotype("+{DELAY 5}plus^carat~@{}}")]
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
        self.assertTrue(callable(KM.token_command('{DELAY 5}')))
        self.assertFalse(callable(KM.token_command('{DELAY 5 }')))
        self.assertFalse(callable(KM.token_command('{DELAY 5')))
        self.assertFalse(callable(KM.token_command('{DELAY a }')))
        self.assertFalse(callable(KM.token_command('{DELAY }')))
        self.assertFalse(callable(KM.token_command('{DELAY}')))
        self.assertFalse(callable(KM.token_command('DELAY 5}')))
        self.assertFalse(callable(KM.token_command('{DELAY a}')))

    def test_hotp(self):
        # adapted from https://github.com/susam/mintotp/blob/master/test.py
        self.assertEqual(KM.hotp(SECRET1, 0), '549419')
        self.assertEqual(KM.hotp(SECRET2, 0), '009551')
        self.assertEqual(KM.hotp(SECRET1, 0, 5, 'sha1', True), '9XFQT')
        self.assertEqual(KM.hotp(SECRET2, 0, 5, 'sha1', True), 'QR5CX')
        self.assertEqual(KM.hotp(SECRET1, 42), '626854')
        self.assertEqual(KM.hotp(SECRET2, 42), '093610')
        self.assertEqual(KM.hotp(SECRET1, 42, 5, 'sha1', True), '25256')
        self.assertEqual(KM.hotp(SECRET2, 42, 5, 'sha1', True), 'RHH8D')

    def test_totp(self):
        # adapted from https://github.com/susam/mintotp/blob/master/test.py
        with mock.patch('time.time', return_value=0):
            self.assertEqual(KM.totp(SECRET1), '549419')
            self.assertEqual(KM.totp(SECRET2), '009551')
            self.assertEqual(KM.totp(SECRET1, 30, 5, 'sha1', True), '9XFQT')
            self.assertEqual(KM.totp(SECRET2, 30, 5, 'sha1', True), 'QR5CX')
        with mock.patch('time.time', return_value=10):
            self.assertEqual(KM.totp(SECRET1), '549419')
            self.assertEqual(KM.totp(SECRET2), '009551')
            self.assertEqual(KM.totp(SECRET1, 30, 5, 'sha1', True), '9XFQT')
            self.assertEqual(KM.totp(SECRET2, 30, 5, 'sha1', True), 'QR5CX')
        with mock.patch('time.time', return_value=1260):
            self.assertEqual(KM.totp(SECRET1), '626854')
            self.assertEqual(KM.totp(SECRET2), '093610')
            self.assertEqual(KM.totp(SECRET1, 30, 5, 'sha1', True), '25256')
            self.assertEqual(KM.totp(SECRET2, 30, 5, 'sha1', True), 'RHH8D')
        with mock.patch('time.time', return_value=1270):
            self.assertEqual(KM.totp(SECRET1), '626854')
            self.assertEqual(KM.totp(SECRET2), '093610')
            self.assertEqual(KM.totp(SECRET1, 30, 5, 'sha1', True), '25256')
            self.assertEqual(KM.totp(SECRET2, 30, 5, 'sha1', True), 'RHH8D')

    def test_gen_otp(self):
        otp_url = "otpauth://totp/{name}:none?secret={secret}&period={period}&digits={digits}"
        with mock.patch('time.time', return_value=0):
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="test",
                secret=SECRET1,
                period=30,
                digits=6
            )), '549419')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="test",
                secret=SECRET2,
                period=30,
                digits=6
            )), '009551')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="Steam",
                secret=SECRET1,
                period=30,
                digits=5
            ) + "&encoder=steam"), '9XFQT')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="Steam",
                secret=SECRET2,
                period=30,
                digits=5
            ) + "&encoder=steam"), 'QR5CX')

        with mock.patch('time.time', return_value=1260):
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="test",
                secret=SECRET1,
                period=30,
                digits=6
            )), '626854')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="test",
                secret=SECRET2,
                period=30,
                digits=6
            )), '093610')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="Steam",
                secret=SECRET1,
                period=30,
                digits=5
            ) + "&encoder=steam"), '25256')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="Steam",
                secret=SECRET2,
                period=30,
                digits=5
            ) + "&encoder=steam"), 'RHH8D')

        with mock.patch('time.time', return_value=1270):
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="test",
                secret=SECRET1,
                period=30,
                digits=6
            )), '626854')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="test",
                secret=SECRET2,
                period=30,
                digits=6
            )), '093610')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="Steam",
                secret=SECRET1,
                period=30,
                digits=5
            ) + "&encoder=steam"), '25256')
            self.assertEqual(KM.gen_otp(otp_url.format(
                name="Steam",
                secret=SECRET2,
                period=30,
                digits=5
            ) + "&encoder=steam"), 'RHH8D')


if __name__ == "__main__":
    unittest.main()
