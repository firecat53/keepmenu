"""Unit tests for keepmenu

"""
import imp
from multiprocessing.managers import BaseManager
import os
from shutil import copyfile, rmtree
import socket
import string
import sys
import tempfile
import unittest

KM = imp.load_source('*', 'keepmenu')

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

    def test_generate_password(self):
        """Test generate_password function

        """
        # args = (length, use_digits T/F, use special chars T/F)
        values = [(0, True, True),
                  (2, False, False),
                  (10, True, True),
                  (20, False, True),
                  (1000, True, False),
                  (50, False, False),
                  ()]
        for args in values:
            pword = KM.gen_passwd(*args)
            if not args:
                args = (20, True, True)  ## Defaults for gen_passwd
            self.assertTrue(len(pword) == args[0] or len(pword) == 4)
            if args[1] is True:
                self.assertTrue(any(c.isdigit() for c in pword))
            else:
                self.assertFalse(any(c.isdigit() for c in pword))
            if args[2] is True:
                self.assertTrue(any(c in string.punctuation for c in pword))
            else:
                self.assertFalse(any(c in string.punctuation for c in pword))

    def test_conf(self):
        """Test generating config file when none exists

        """
        KM.process_config()
        self.assertTrue(KM.CONF.has_section("dmenu"))
        self.assertTrue(KM.CONF.has_section("dmenu_passphrase"))
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "nf") and
                        KM.CONF.get("dmenu_passphrase", "nf") == "#222222")
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "nb") and
                        KM.CONF.get("dmenu_passphrase", "nb") == "#222222")
        self.assertTrue(KM.CONF.has_option("dmenu_passphrase", "rofi_obscure") and
                        KM.CONF.get("dmenu_passphrase", "rofi_obscure") ==
                        "True")
        self.assertTrue(KM.CONF.has_section("database"))
        self.assertTrue(KM.CONF.has_option("database", "database_1"))
        self.assertTrue(KM.CONF.has_option("database", "keyfile_1"))
        self.assertTrue(KM.CONF.has_option("database", "pw_cache_period_min") and
                        KM.CONF.get("database", "pw_cache_period_min") == \
                                str(KM.CACHE_PERIOD_DEFAULT_MIN))

    def test_dmenu_cmd(self):
        """Test proper reading of dmenu command string from config.ini

        """
        # First test default config
        KM.process_config()
        self.assertTrue(KM.dmenu_cmd(10, "Entries") == \
                ["dmenu", "-i", "-l", "10", "-p", "Entries"])
        # Test full config
        copyfile("tests/keepmenu-config.ini", KM.CONF_FILE)
        KM.process_config()
        if sys.version_info.major < 3:
            res = ['/usr/bin/rofi', '-i', '-dmenu', '-lines', '10', '-p',
                   u'Passphrase', '-password', u'-b', u'-nb', u'#222222',
                   u'-nf', u'#222222', u'-sb', u'#123456', u'-fn',
                   u'Inconsolata-12']
        else:
            res = ["/usr/bin/rofi", "-i", "-dmenu", "-lines", "10", "-p", "Passphrase",
                   "-password", "-fn", "Inconsolata-12", "-nb", "#222222", "-nf", "#222222",
                   "-sb", "#123456", "-b"]
        self.assertTrue(KM.dmenu_cmd(20, "Passphrase") == res)

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
        self.assertTrue(database == (db_name, '', 'password'))
        kpo = KM.get_entries(database)
        self.assertIsInstance(kpo, KM.PyKeePass)



if __name__ == "__main__":
    unittest.main()
