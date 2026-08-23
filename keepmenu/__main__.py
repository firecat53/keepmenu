"""Main entrypoint and CLI parsing

"""
import argparse
import configparser
from contextlib import closing, contextmanager, suppress
import multiprocessing
from multiprocessing import AuthenticationError, Event, Process, Pipe
from getpass import getpass
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser
import secrets
import signal
import socket
from subprocess import call
import sys

import keepmenu
from keepmenu.keepmenu import DmenuRunner

# Python 3.14 changes the default to 'forkserver' on Linux.
# Set to 'fork' for backward compatibility.
multiprocessing.set_start_method('fork')

# Seconds to wait for a daemon to answer, both when connecting and during the
# BaseManager handshake. It is a loopback connection answered by a dedicated
# thread, so a daemon that is busy still replies immediately. Anything slower
# is a process that isn't our daemon, and waiting on it is what used to hang
# keepmenu for minutes when a dead daemon's port had been taken over.
DAEMON_CONNECT_TIMEOUT = 2


def find_free_port():
    """Find random free port to use for BaseManager server

    Returns: int Port

    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))  # pylint:disable=no-member
        return sock.getsockname()[1]  # pylint:disable=no-member

def port_in_use(port, timeout=DAEMON_CONNECT_TIMEOUT):
    """Return Boolean

    A listening socket whose owner has stopped accepting leaves connect()
    retrying for minutes, so this gives up and reports the port unusable
    instead.

    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            return s.connect_ex(('127.0.0.1', port)) == 0
        except OSError:
            return False

def get_auth(create=True):
    """Generate and save port and authkey to runtime directory.

    Uses $XDG_RUNTIME_DIR/keepmenu/ if available,
    Otherwise falls back to $TMPDIR/keepmenu-<uid>/.

    Args: create - bool, write a new auth file if there isn't one. False for
                   the runs that only look for a daemon and never start one, so
                   they don't leave an auth file (and its authkey) behind
                   pointing at a port nothing is listening on.

    Returns: int port, bytestring authkey. (None, None) when create is False
             and there is no auth file, which means no daemon is running: the
             daemon writes the file before it starts and removes it when it
             exits.

    """
    auth = configparser.ConfigParser()
    if create is False and not exists(keepmenu.AUTH_FILE):
        return None, None
    try:
        # O_EXCL|O_NOFOLLOW so that a file or symlink planted by another user
        # can never be written to or followed. O_EXCL also means a concurrent
        # instance can't have the file half written when we read it below.
        fd_ = os.open(keepmenu.AUTH_FILE,
                      os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600)
    except FileExistsError:
        pass
    else:
        with open(fd_, 'w', encoding=keepmenu.ENC) as a_file:
            auth.set('DEFAULT', 'port', str(find_free_port()))
            auth.set('DEFAULT', 'authkey', random_str())
            auth.write(a_file)
    keepmenu.insecure_path_exit(keepmenu.AUTH_FILE, isdir=False)
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

    The BaseManager RPC is pickle based, so this key is what keeps another
    local user from running code in the daemon. It needs a CSPRNG.

    Returns: string

    """
    return secrets.token_hex(32)


@contextmanager
def time_limit(seconds):
    """Raise TimeoutError if the wrapped block runs longer than `seconds`

    The BaseManager handshake is a blocking read that no socket timeout
    reaches: multiprocessing puts the socket back in blocking mode before
    connecting, and then waits for a challenge. An unrelated process holding
    the port never sends one, so without this the wait never ends.

    """
    def _timed_out(_signum, _frame):
        raise TimeoutError("timed out")

    try:
        old = signal.signal(signal.SIGALRM, _timed_out)
    except (AttributeError, ValueError):
        # No SIGALRM, or not the main thread, so the block runs unbounded
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def connect_to_daemon(port, auth):
    """Connect to the BaseManager of a running daemon

    A bare connect only proves that something is listening. The port from an
    auth file left by a daemon that died may since have been taken by an
    unrelated process, which is not a daemon no matter what it does with the
    connection.

    Args: port - int or None, from the auth file
          auth - bytestring authkey

    Returns: BaseManager object, or None if no daemon is listening on port

    """
    if port is None:
        return None
    try:
        with time_limit(DAEMON_CONNECT_TIMEOUT):
            return client(port, auth)
    except (TimeoutError, AuthenticationError, EOFError, OSError):
        return None


def client(port, auth):
    """Define client connection to server BaseManager

    Returns: BaseManager object
    """
    mgr = BaseManager(address=('', port), authkey=auth)
    mgr.register('set_event')
    mgr.register('get_pipe')
    mgr.register('read_args_from_pipe')
    mgr.register('totp_mode')
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
        self._parent_conn, self._child_conn = Pipe(duplex=True)
        self.shared_state = shared_state

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

    server = None
    try:
        server = Server(shared_state=shared_state)
        if kwargs.get('totp'):
            server.totp_flag.set()
        dmenu = DmenuRunner(server, shared_state=shared_state, **kwargs)
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


def print_show_result(result):
    """Print the result of a --show request and exit non-zero on error.

    Args: result - string from run_once or from the daemon. None on failure, an
                   'ERROR: ' prefixed message on a reported error, and an empty
                   string when there is nothing to print (clipboard mode).

    """
    if result is None:
        sys.exit(1)
    if result.startswith("ERROR:"):
        print(result[7:], file=sys.stderr)  # Strip "ERROR: " prefix
        sys.exit(1)
    if result:
        print(result)


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
        "-f",
        "--field",
        type=str,
        action="append",
        required=False,
        metavar="FIELD",
        help="Field to output with --show. Repeat for multiple fields, in order. "
             "Example: -f title -f username -f S:<attribute>. "
             "Use 'all' to print every field with a value. Defaults to password",
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
        "-l",
        "--lock",
        action="store_true",
        default=False,
        required=False,
        help="Lock all open databases and stop the daemon",
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
            help="Output the password of the matched entry or the fields given by --field",
    )

    parser.add_argument(
            "-n",
            "--no-prompt",
            action="store_true",
            default = False,
            required=False,
            help="Do not prompt for database password",
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"keepmenu {keepmenu.__version__}",
        help="Show version and exit",
    )

    args = vars(parser.parse_args())
    if args["field"] and not args["show"]:
        parser.error("--field requires --show")

    # Only a run that may start a daemon creates the auth file. --lock and
    # --show just need to find one, and an auth file left behind by a run that
    # started nothing sends a later invocation at a port that is dead, or that
    # some unrelated process has since taken.
    port, auth = get_auth(create=not (args["lock"] or args["show"]))
    listening = port is not None and port_in_use(port) is True
    manager = connect_to_daemon(port, auth) if listening else None
    if manager is None:
        if listening:
            # Something is listening on that port, but it is not our daemon, so
            # the auth file is a leftover whose port has been reused. Remove it
            # rather than sending this run, and every later one, at a stranger.
            with suppress(OSError):
                os.remove(keepmenu.AUTH_FILE)
        if args["lock"]:
            # No daemon means nothing is unlocked. Falling through to run()
            # would start one and open a database - the opposite of what was
            # asked.
            return
        if args["show"]:
            # If no server is running, just run directly in one-shot mode
            from keepmenu.run_once import run_once
            keepmenu.CLI = True
            print_show_result(run_once(return_errors=True, **args))
            return
        run(**args)
        return
    try:
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
        if args["lock"]:
            # The daemon locks and exits immediately, taking the manager
            # connection down mid-call. That's success, not an error.
            with suppress(EOFError, ConnectionError):
                manager.set_event()  # pylint: disable=no-member
            return
        manager.set_event()  # pylint: disable=no-member
        if args["show"]:
            # Wait for daemon to process and send back result through pipe
            result = manager.receive_show_result()  # pylint: disable=no-member
            # AutoProxy objects need _getvalue() to get the actual string
            if hasattr(result, '_getvalue'):
                result = result._getvalue()
            print_show_result(result)
    except ConnectionRefusedError:
        # Don't print the ConnectionRefusedError if any other exceptions are
        # raised.
        pass


if __name__ == '__main__':
    main()

# vim: set et ts=4 sw=4 :
