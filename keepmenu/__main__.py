"""Main entrypoint and CLI parsing

"""
import argparse
import configparser
from contextlib import closing
from multiprocessing import Event, Process, Pipe
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser
import random
import socket
import string
from subprocess import call
import sys

import keepmenu
from keepmenu.keepmenu import DmenuRunner


def find_free_port():
    """Find random free port to use for BaseManager server

    Returns: int Port

    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))  # pylint:disable=no-member
        return sock.getsockname()[1]  # pylint:disable=no-member

def port_in_use(port):
    """Return Boolean

    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def get_auth():
    """Generate and save port and authkey to ~/.cache/.keepmenu-auth

    Returns: int port, bytestring authkey

    """
    auth = configparser.ConfigParser()
    if not exists(keepmenu.AUTH_FILE):
        fd_ = os.open(keepmenu.AUTH_FILE, os.O_WRONLY | os.O_CREAT, 0o600)
        with open(fd_, 'w', encoding=keepmenu.ENC) as a_file:
            auth.set('DEFAULT', 'port', str(find_free_port()))
            auth.set('DEFAULT', 'authkey', random_str())
            auth.write(a_file)
    try:
        auth.read(keepmenu.AUTH_FILE)
        port = auth.get('DEFAULT', 'port')
        authkey = auth.get('DEFAULT', 'authkey').encode()
    except (configparser.NoOptionError, configparser.MissingSectionHeaderError):
        os.remove(keepmenu.AUTH_FILE)
        print("Cache file was corrupted. Stopping all instances. Please try again")
        call(["pkill", "keepmenu"])  # Kill all prior instances as well
        return None, None
    return int(port), authkey


def random_str():
    """Generate random auth string for BaseManager

    Returns: string

    """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(15))


def client(port, auth):
    """Define client connection to server BaseManager

    Returns: BaseManager object
    """
    mgr = BaseManager(address=('', port), authkey=auth)
    mgr.register('set_event')
    mgr.register('get_pipe')
    mgr.register('read_args_from_pipe')
    mgr.register('totp_mode')
    mgr.connect()

    return mgr


class Server(Process):  # pylint: disable=too-many-instance-attributes
    """Run BaseManager server to listen for dmenu calling events

    """
    def __init__(self):
        Process.__init__(self)
        self.port, self.authkey = get_auth()
        self.start_flag = Event()
        self.kill_flag = Event()
        self.cache_time_expired = Event()
        self.args_flag = Event()
        self.totp_flag = Event()
        self.start_flag.set()
        self.args = None
        self._parent_conn, self._child_conn = Pipe(duplex=False)

    def run(self):
        _ = self.server()
        try:
            self.kill_flag.wait()
        except KeyboardInterrupt:
            self.kill_flag.set()

    def _get_pipe(self):
        return self._child_conn

    def get_args(self):
        """ Reads aruments sent by the client to the server

        """
        return self._parent_conn.recv()

    def server(self):
        """Set up BaseManager server

        """
        mgr = BaseManager(address=('127.0.0.1', self.port),
                          authkey=self.authkey)
        mgr.register('set_event', callable=self.start_flag.set)
        mgr.register('get_pipe', callable=self._get_pipe)
        mgr.register('read_args_from_pipe', callable=self.args_flag.set)
        mgr.register('totp_mode', callable=self.totp_flag.set)
        mgr.start()  # pylint: disable=consider-using-with
        return mgr


def run(**kwargs):
    """Start the background Manager and Dmenu runner processes.

    """
    server = Server()
    if kwargs.get('totp'):
        server.totp_flag.set()
    dmenu = DmenuRunner(server, **kwargs)
    dmenu.daemon = True
    server.start()
    dmenu.start()
    try:
        server.join()
    except KeyboardInterrupt:
        sys.exit()
    finally:
        if exists(expanduser(keepmenu.AUTH_FILE)):
            os.remove(expanduser(keepmenu.AUTH_FILE))


def main():
    """Main script entrypoint

    """
    parser = argparse.ArgumentParser(
        description="Dmenu (or compatible launcher) frontend for Keepass databases")

    parser.add_argument(
        "-a",
        "--autotype",
        type=str,
        required=False,
        help="Override autotype sequence in config.ini",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=False,
        help="File path to a config file",
    )

    parser.add_argument(
        "-C",
        "--clipboard",
        action="store_true",
        default=False,
        required=False,
        help="Copy values to clipboard instead of typing.",
    )

    parser.add_argument(
        "-d",
        "--database",
        type=str,
        required=False,
        help="File path to a database to open, skipping the database selection menu",
    )

    parser.add_argument(
        "-k",
        "--keyfile",
        type=str,
        required=False,
        help="File path of the keyfile needed to open the database specified by --database/-d",
    )

    parser.add_argument(
        "-t",
        "--totp",
        action='store_true',
        required=False,
        help="TOTP mode",
    )

    args = vars(parser.parse_args())

    port, auth = get_auth()
    if port_in_use(port) is False:
        run(**args)
    try:
        manager = client(port, auth)
        conn = manager.get_pipe()  # pylint: disable=no-member
        if args.get('totp'):
            manager.totp_mode()  # pylint: disable=no-member
        if any(args.values()):
            conn.send(args)
            manager.read_args_from_pipe()  # pylint: disable=no-member
        manager.set_event()  # pylint: disable=no-member
    except ConnectionRefusedError:
        # Don't print the ConnectionRefusedError if any other exceptions are
        # raised.
        pass


if __name__ == '__main__':
    main()

# vim: set et ts=4 sw=4 :
