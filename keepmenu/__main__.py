"""Main entrypoint and CLI parsing

"""
import argparse
import configparser
from contextlib import closing
import multiprocessing
from multiprocessing import Event, Process, Pipe
from getpass import getpass
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser
import random
import socket
import string
from subprocess import call

import keepmenu
from keepmenu.keepmenu import DmenuRunner

# Python 3.14 changes the default to 'forkserver' on Linux.
# Set to 'fork' for backward compatibility.
multiprocessing.set_start_method('fork')


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
    """Generate and save port and authkey to runtime directory.

    Uses $XDG_RUNTIME_DIR/keepmenu/ if available,
    Otherwise falls back to $TMPDIR/keepmenu-<uid>/.

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
    mgr.register('get_current_database_path')
    mgr.register('get_open_database_paths')
    mgr.register('get_config_passwordable_paths')
    mgr.register('receive_show_result')
    mgr.connect()

    return mgr


class Server(Process):  # pylint: disable=too-many-instance-attributes
    """Run BaseManager server to listen for dmenu calling events

    """
    def __init__(self, shared_state=None):
        Process.__init__(self)
        self.port, self.authkey = get_auth()
        self.start_flag = Event()
        self.kill_flag = Event()
        self.cache_time_expired = Event()
        self.args_flag = Event()
        self.totp_flag = Event()
        self.start_flag.set()
        self.args = None
        self.current_database_path = None
        self._parent_conn, self._child_conn = Pipe(duplex=True)
        self.shared_state = shared_state
        self.open_database_paths = set()
        self.config_passwordable_paths = set()

    def run(self):
        _ = self.server()
        try:
            self.kill_flag.wait()
        except KeyboardInterrupt:
            self.kill_flag.set()

    def _get_pipe(self):
        # Pass arguments from client to server
        return self._child_conn

    def get_args(self):
        """ Reads aruments sent by the client to the server

        """
        return self._parent_conn.recv()

    def receive_show_result(self, timeout=30):
        """Receive the show result from the daemon through the pipe.

        Args:
            timeout: Maximum seconds to wait for result

        Returns:
            The result string or None if timeout/error
        """
        if self._child_conn.poll(timeout):
            return self._child_conn.recv()
        return None

    def server(self):
        """Set up BaseManager server

        """
        mgr = BaseManager(address=('127.0.0.1', self.port),
                          authkey=self.authkey)
        def _get_open_paths():
            if self.shared_state:
                return list(self.shared_state.open_database_paths)
            return []

        def _get_config_paths():
            if self.shared_state:
                return list(self.shared_state.config_passwordable_paths)
            return []

        mgr.register('set_event', callable=self.start_flag.set)
        mgr.register('get_pipe', callable=self._get_pipe)
        mgr.register('read_args_from_pipe', callable=self.args_flag.set)
        mgr.register('totp_mode', callable=self.totp_flag.set)
        mgr.register('get_current_database_path',
                     callable=lambda: self.shared_state.current_database_path if self.shared_state else None)
        mgr.register('get_open_database_paths', callable=_get_open_paths)
        mgr.register('get_config_passwordable_paths', callable=_get_config_paths)
        mgr.register('receive_show_result', callable=self.receive_show_result)
        mgr.start()  # pylint: disable=consider-using-with
        return mgr


def run(**kwargs):
    """Start the background Manager and Dmenu runner processes.

    """
    # Create shared state manager for cross-process communication
    state_manager = multiprocessing.Manager()
    shared_state = state_manager.Namespace()
    shared_state.open_database_paths = []
    shared_state.config_passwordable_paths = []
    shared_state.current_database_path = None

    server = None
    try:
        server = Server(shared_state=shared_state)
        if kwargs.get('totp'):
            server.totp_flag.set()
        dmenu = DmenuRunner(server, shared_state=shared_state, **kwargs)
        # Set the initial database path registered for the server callable
        if dmenu.database and dmenu.database.dbase:
            shared_state.current_database_path = dmenu.database.dbase
        dmenu.daemon = True
        server.start()
        dmenu.start()
        server.join()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None and server.is_alive():
            server.terminate()
        if exists(expanduser(keepmenu.AUTH_FILE)):
            os.remove(expanduser(keepmenu.AUTH_FILE))
    return dmenu


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

    parser.add_argument(
            "-s",
            "--show",
            type=str,
            required=False,
            help="Return password of matched entry",
    )

    parser.add_argument(
            "-n",
            "--no-prompt",
            action="store_true",
            default = False,
            required=False,
            help="Do not prompt for database password",
    )

    args = vars(parser.parse_args())

    port, auth = get_auth()
    if port_in_use(port) is False and not args["show"]:
        run(**args)
    elif port_in_use(port) is False and args["show"]:
        # If no server is running, just run directly in one-shot mode
        from keepmenu.run_once import run_once
        password = run_once(**args)
        if password:
            print(password)
        return
    try:
        manager = client(port, auth)
        conn = manager.get_pipe()  # pylint: disable=no-member
        if args["show"] and args.get("database"):
            req_path = os.path.realpath(os.path.expanduser(args["database"]))
            try:
                open_paths_result = manager.get_open_database_paths()
                # AutoProxy objects need _getvalue() to get the actual list
                open_paths = set(open_paths_result._getvalue() if hasattr(open_paths_result, '_getvalue') else open_paths_result)
                cfg_pw_paths_result = manager.get_config_passwordable_paths()
                cfg_pw_paths = set(cfg_pw_paths_result._getvalue() if hasattr(cfg_pw_paths_result, '_getvalue') else cfg_pw_paths_result)
            except Exception:
                open_paths, cfg_pw_paths = set(), set()

            if (req_path not in open_paths) and (req_path not in cfg_pw_paths) and not args.get("no_prompt"):
                # Prompt in client context
                args["password"] = getpass()

        if args.get('totp'):
            manager.totp_mode()  # pylint: disable=no-member
        if any(args.values()):
            conn.send(args)
            manager.read_args_from_pipe()  # pylint: disable=no-member
        manager.set_event()  # pylint: disable=no-member
        if args["show"]:
            # Wait for daemon to process and send back result through pipe
            result = manager.receive_show_result()  # pylint: disable=no-member
            # AutoProxy objects need _getvalue() to get the actual string
            if hasattr(result, '_getvalue'):
                result = result._getvalue()
            if result:
                if result.startswith("ERROR:"):
                    print(result[7:], file=sys.stderr)  # Strip "ERROR: " prefix
                else:
                    print(result)
    except ConnectionRefusedError:
        # Don't print the ConnectionRefusedError if any other exceptions are
        # raised.
        pass


if __name__ == '__main__':
    main()

# vim: set et ts=4 sw=4 :
