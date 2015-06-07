#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013, 2014  James E. Carpenter
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import socket
import sys
import os
import select
try:
    import fcntl
    import termios
    import tty
except ImportError:
    # On windows it's not available but this module can be included by the test suite
    pass
import struct
import time
import argparse
import traceback


import logging
log = logging.getLogger(__name__)


# Escape characters
ESC_CHAR = '^^'         # can be overriden from command line
ESC_QUIT = 'q'

# IOU seems to only send *1* byte at a time. If
# they ever fix that we'll be ready for it.
BUFFER_SIZE = 1024

# How long to wait before retrying a connection (seconds)
RETRY_DELAY = 3

# How often to test an idle connection (seconds)
POLL_TIMEOUT = 3


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_ABORT = 2

# Mostly from:
# https://code.google.com/p/miniboa/source/browse/trunk/miniboa/telnet.py
# --[ Telnet Commands ]---------------------------------------------------------
SE = 240  # End of sub-negotiation parameters
NOP = 241  # No operation
DATMK = 242  # Data stream portion of a sync.
BREAK = 243  # NVT Character BRK
IP = 244  # Interrupt Process
AO = 245  # Abort Output
AYT = 246  # Are you there
EC = 247  # Erase Character
EL = 248  # Erase Line
GA = 249  # The Go Ahead Signal
SB = 250  # Sub-option to follow
WILL = 251  # Will; request or confirm option begin
WONT = 252  # Wont; deny option request
DO = 253  # Do = Request or confirm remote option
DONT = 254  # Don't = Demand or confirm option halt
IAC = 255  # Interpret as Command
SEND = 1   # Sub-process negotiation SEND command
IS = 0   # Sub-process negotiation IS command
# --[ Telnet Options ]----------------------------------------------------------
BINARY = 0   # Transmit Binary
ECHO = 1   # Echo characters back to sender
RECON = 2   # Reconnection
SGA = 3   # Suppress Go-Ahead
TMARK = 6   # Timing Mark
TTYPE = 24  # Terminal Type
NAWS = 31  # Negotiate About Window Size
LINEMO = 34  # Line Mode


class FileLock:

    # struct flock {       /* from fcntl(2) */
    #     ...
    #     short l_type;    /* Type of lock: F_RDLCK,
    #                         F_WRLCK, F_UNLCK */
    #     short l_whence;  /* How to interpret l_start:
    #                         SEEK_SET, SEEK_CUR, SEEK_END */
    #     off_t l_start;   /* Starting offset for lock */
    #     off_t l_len;     /* Number of bytes to lock */
    #     pid_t l_pid;     /* PID of process blocking our lock
    #                         (F_GETLK only) */
    #     ...
    # };
    _flock = struct.Struct('hhqql')

    def __init__(self, fname=None):
        self.fd = None
        self.fname = fname

    def get_lock(self):
        flk = self._flock.pack(fcntl.F_WRLCK, os.SEEK_SET,
                               0, 0, os.getpid())
        flk = self._flock.unpack(
            fcntl.fcntl(self.fd, fcntl.F_GETLK, flk))

        # If it's not locked (or is locked by us) then return None,
        # otherwise return the PID of the owner.
        if flk[0] == fcntl.F_UNLCK:
            return None
        return flk[4]

    def lock(self):
        try:
            self.fd = open('{}.lck'.format(self.fname), 'a')
        except Exception as e:
            raise LockError("Couldn't get lock on {}: {}"
                            .format(self.fname, e))

        flk = self._flock.pack(fcntl.F_WRLCK, os.SEEK_SET, 0, 0, 0)
        try:
            fcntl.fcntl(self.fd, fcntl.F_SETLK, flk)
        except BlockingIOError:
            raise LockError("Already connected. PID {} has lock on {}"
                            .format(self.get_lock(), self.fname))

        # If we got here then we must have the lock. Store the PID.
        self.fd.truncate(0)
        self.fd.write('{}\n'.format(os.getpid()))
        self.fd.flush()

    def unlock(self):
        if self.fd:
            # Deleting first prevents a race condition
            try:
                os.unlink(self.fd.name)
            except FileNotFoundError as e:
                log.debug("{}".format(e))
            self.fd.close()

    def __enter__(self):
        self.lock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()
        return False


class Console:

    def fileno(self):
        raise NotImplementedError("Only routers have fileno()")


class TTY(Console):

    def read(self, fileno, bufsize):
        return self.fd.read(bufsize)

    def write(self, buf):
        return self.fd.write(buf)

    def register(self, epoll):
        self.epoll = epoll
        epoll.register(self.fd, select.EPOLLIN | select.EPOLLET)

    def unregister(self, epoll):
        epoll.unregister(self.fd)

    def __enter__(self):
        try:
            self.fd = open('/dev/tty', 'r+b', buffering=0)
        except OSError as e:
            raise TTYError("Couldn't open controlling TTY: {}".format(e))

        # Save original flags
        self.termios = termios.tcgetattr(self.fd)
        self.fcntl = fcntl.fcntl(self.fd, fcntl.F_GETFL)

        # Update flags
        tty.setraw(self.fd, termios.TCSANOW)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.fcntl | os.O_NONBLOCK)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        # Restore flags to original settings
        termios.tcsetattr(self.fd, termios.TCSANOW, self.termios)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.fcntl)

        self.fd.close()

        return False


class TelnetServer(Console):

    def __init__(self, addr, port, stop_event):
        self.addr = addr
        self.port = port
        self.fd_dict = {}
        self.stop_event = stop_event

    def read(self, fileno, bufsize):
        # Someone wants to connect?
        if fileno == self.sock_fd.fileno():
            self._accept()
            return None

        self._cur_fileno = fileno

        # Read a maximum of _bufsize_ bytes without blocking. When it
        # would want to block it means there's no more data. An empty
        # buffer normally means that we've been disconnected.
        try:
            buf = self._read_cur(bufsize, socket.MSG_DONTWAIT)
        except BlockingIOError:
            return None
        except ConnectionResetError:
            buf = b''
        if not buf:
            self._disconnect(fileno)

        # Process and remove any telnet commands from the buffer
        if IAC in buf:
            buf = self._IAC_parser(buf)

        return buf

    def write(self, buf):
        for fd in self.fd_dict.values():
            fd.send(buf)

    def register(self, epoll):
        self.epoll = epoll
        epoll.register(self.sock_fd, select.EPOLLIN)

    def unregister(self, epoll):
        epoll.unregister(self.sock_fd)

    def _read_block(self, bufsize):
        buf = self._read_cur(bufsize, socket.MSG_WAITALL)
        # If we don't get everything we were looking for then the
        # client probably disconnected.
        if len(buf) < bufsize:
            self._disconnect(self._cur_fileno)
        return buf

    def _read_cur(self, bufsize, flags):
        return self.fd_dict[self._cur_fileno].recv(bufsize, flags)

    def _write_cur(self, buf):
        return self.fd_dict[self._cur_fileno].send(buf)

    def _IAC_parser(self, buf):
        skip_to = 0
        while not self.stop_event.is_set():
            # Locate an IAC to process
            iac_loc = buf.find(IAC, skip_to)
            if iac_loc < 0:
                break

            # Get the TELNET command
            iac_cmd = bytearray([IAC])
            try:
                iac_cmd.append(buf[iac_loc + 1])
            except IndexError:
                buf.extend(self._read_block(1))
                iac_cmd.append(buf[iac_loc + 1])

            # Is this just a 2-byte TELNET command?
            if iac_cmd[1] not in [WILL, WONT, DO, DONT]:
                if iac_cmd[1] == AYT:
                    log.debug("Telnet server received Are-You-There (AYT)")
                    self._write_cur(
                        b'\r\nYour Are-You-There received. I am here.\r\n'
                    )
                elif iac_cmd[1] == IAC:
                    # It's data, not an IAC
                    iac_cmd.pop()
                    # This prevents the 0xff from being
                    # interputed as yet another IAC
                    skip_to = iac_loc + 1
                    log.debug("Received IAC IAC")
                elif iac_cmd[1] == NOP:
                    pass
                else:
                    log.debug("Unhandled telnet command: "
                              "{0:#x} {1:#x}".format(*iac_cmd))

            # This must be a 3-byte TELNET command
            else:
                try:
                    iac_cmd.append(buf[iac_loc + 2])
                except IndexError:
                    buf.extend(self._read_block(1))
                    iac_cmd.append(buf[iac_loc + 2])
                # We do ECHO, SGA, and BINARY. Period.
                if iac_cmd[1] == DO:
                    if iac_cmd[2] not in [ECHO, SGA, BINARY]:
                        self._write_cur(bytes([IAC, WONT, iac_cmd[2]]))
                        log.debug("Telnet WON'T {:#x}".format(iac_cmd[2]))
                elif iac_cmd[1] == WILL and iac_cmd[2] == BINARY:
                    pass  # It's standard negociation we can ignore it
                else:
                    log.debug("Unhandled telnet command: "
                              "{0:#x} {1:#x} {2:#x}".format(*iac_cmd))

            # Remove the entire TELNET command from the buffer
            buf = buf.replace(iac_cmd, b'', 1)

        # Return the new copy of the buffer, minus telnet commands
        return buf

    def _accept(self):
        fd, addr = self.sock_fd.accept()
        self.fd_dict[fd.fileno()] = fd
        self.epoll.register(fd, select.EPOLLIN | select.EPOLLET)

        log.info("Telnet connection from {}:{}".format(addr[0], addr[1]))

        # This is a one-way negotiation. This is very basic so there
        # shouldn't be any problems with any decent client.
        fd.send(bytes([IAC, WILL, ECHO,
                       IAC, WILL, SGA,
                       IAC, WILL, BINARY,
                       IAC, DO, BINARY]))

        if args.telnet_limit and len(self.fd_dict) > args.telnet_limit:
            fd.send(b'\r\nToo many connections\r\n')
            self._disconnect(fd.fileno())
            log.warn("Client disconnected because of too many connections. "
                     "(limit currently {})".format(args.telnet_limit))

    def _disconnect(self, fileno):
        fd = self.fd_dict.pop(fileno)
        log.info("Telnet client disconnected")
        try:
            fd.shutdown(socket.SHUT_RDWR)
        except OSError as e:
            log.warn("shutdown: {}".format(e))
        fd.close()

    def __enter__(self):
        # Open a socket and start listening

        info = socket.getaddrinfo(self.addr, self.port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
        if not info:
            raise TelnetServerError("getaddrinfo returns an empty list on {}:{}".format(self.addr, self.port))
        for res in info:
            af, socktype, proto, _, sa = res
            sock_fd = socket.socket(af, socktype, proto)
            sock_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock_fd.bind(sa)
            except OSError:
                raise TelnetServerError("Cannot bind to {}:{}"
                                        .format(self.addr, self.port))

        sock_fd.listen(socket.SOMAXCONN)
        self.sock_fd = sock_fd
        log.info("Telnet server ready for connections on {}:{}".format(self.addr, self.port))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for fileno in list(self.fd_dict.keys()):
            self._disconnect(fileno)
        self.sock_fd.close()
        return False


class IOU:

    def __init__(self, ttyC, ttyS, stop_event):
        self.ttyC = ttyC
        self.ttyS = ttyS
        self.stop_event = stop_event

    def read(self, bufsize):
        try:
            buf = self.fd.recv(bufsize)
        except BlockingIOError:
            return None
        return buf

    def write(self, buf):
        try:
            self.fd.send(buf)
        except BlockingIOError:
            return

    def _open(self):
        self.fd = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.fd.setblocking(False)

    def _bind(self):
        try:
            os.unlink(self.ttyC)
        except FileNotFoundError:
            pass
        except Exception as e:
            raise NetioError("Couldn't unlink socket {}: {}".format(self.ttyC, e))

        try:
            self.fd.bind(self.ttyC)
        except Exception as e:
            raise NetioError("Couldn't create socket {}: {}".format(self.ttyC, e))

    def _connect(self):
        # Keep trying until we connect or die trying
        while not self.stop_event.is_set():
            try:
                self.fd.connect(self.ttyS)
            except FileNotFoundError:
                log.debug("Waiting to connect to {}".format(self.ttyS))
                time.sleep(RETRY_DELAY)
            except Exception as e:
                raise NetioError("Couldn't connect to socket {}: {}".format(self.ttyS, e))
            else:
                break

    def register(self, epoll):
        self.epoll = epoll
        epoll.register(self.fd, select.EPOLLIN | select.EPOLLET)

    def unregister(self, epoll):
        epoll.unregister(self.fd)

    def fileno(self):
        return self.fd.fileno()

    def __enter__(self):
        self._open()
        self._bind()
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.unlink(self.ttyC)
        self.fd.close()
        return False


class IOUConError(Exception):
    pass


class LockError(IOUConError):
    pass


class NetioError(IOUConError):
    pass


class TTYError(IOUConError):
    pass


class TelnetServerError(IOUConError):
    pass


class ConfigError(IOUConError):
    pass


def mkdir_netio(netio_dir):
    try:
        os.mkdir(netio_dir)
    except FileExistsError:
        pass
    except Exception as e:
        raise NetioError("Couldn't create directory {}: {}".format(netio_dir, e))


def send_recv_loop(epoll, console, router, esc_char, stop_event):
    router.register(epoll)
    console.register(epoll)

    try:
        router_fileno = router.fileno()
        esc_quit = bytes(ESC_QUIT.upper(), 'ascii')
        esc_state = False

        while not stop_event.is_set():
            event_list = epoll.poll(timeout=POLL_TIMEOUT)

            # When/if the poll times out we send an empty datagram. If IOU
            # has gone away then this will toss a ConnectionRefusedError
            # exception.
            if not event_list:
                router.write(b'')
                continue

            for fileno, event in event_list:
                buf = bytearray()

                # IOU --> tty(s)
                if fileno == router_fileno:
                    while not stop_event.is_set():
                        data = router.read(BUFFER_SIZE)
                        if not data:
                            break
                        buf.extend(data)
                    console.write(buf)

                # tty --> IOU
                else:
                    while not stop_event.is_set():
                        data = console.read(fileno, BUFFER_SIZE)
                        if not data:
                            break
                        buf.extend(data)

                    # If we just received the escape character then
                    # enter the escape state.
                    #
                    # If we are in the escape state then check for a
                    # quit command. Or if it's the escape character then
                    # send the escape character. Else, send the escape
                    # character we ate earlier and whatever character we
                    # just got. Exit escape state.
                    #
                    # If we're not in the escape state and this isn't an
                    # escape character then just send it to IOU.
                    if esc_state:
                        if buf.upper() == esc_quit:
                            sys.exit(EXIT_SUCCESS)
                        elif buf == esc_char:
                            router.write(esc_char)
                        else:
                            router.write(esc_char)
                            router.write(buf)
                        esc_state = False
                    elif buf == esc_char:
                        esc_state = True
                    else:
                        router.write(buf)
    finally:
        router.unregister(epoll)
        console.unregister(epoll)


def get_args():
    parser = argparse.ArgumentParser(
        description='Connect to an IOU console port.')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='display some debugging information')
    parser.add_argument('-e', '--escape',
                        help='set escape character (default: %(default)s)',
                        default=ESC_CHAR, metavar='CHAR')
    parser.add_argument('-t', '--telnet-server',
                        help='start telnet server listening on ADDR:PORT',
                        metavar='ADDR:PORT', default=False)
    parser.add_argument('-l', '--telnet-limit',
                        help='maximum number of simultaneous '
                        'telnet connections (default: %(default)s)',
                        metavar='LIMIT', type=int, default=1)
    parser.add_argument('appl_id', help='IOU instance identifier')
    return parser.parse_args()


def get_escape_character(escape):

    # Figure out the escape character to use.
    # Can be any ASCII character or a spelled out control
    # character, like "^e". The string "none" disables it.
    if escape.lower() == 'none':
        esc_char = b''
    elif len(escape) == 2 and escape[0] == '^':
        c = ord(escape[1].upper()) - 0x40
        if not 0 <= c <= 0x1f:  # control code range
            raise ConfigError("Invalid control code")
        esc_char = bytes([c])
    elif len(escape) == 1:
        try:
            esc_char = bytes(escape, 'ascii')
        except ValueError as e:
            raise ConfigError("Invalid escape character") from e
    else:
        raise ConfigError("Invalid length for escape character")

    return esc_char


def start_ioucon(cmdline_args, stop_event):

    global args
    args = cmdline_args

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        # default logging level
        logging.basicConfig(level=logging.INFO)

    # Create paths for the Unix domain sockets
    netio = '/tmp/netio{}'.format(os.getuid())
    ttyC = '{}/ttyC{}'.format(netio, args.appl_id)
    ttyS = '{}/ttyS{}'.format(netio, args.appl_id)

    try:
        mkdir_netio(netio)
        with FileLock(ttyC):
            esc_char = get_escape_character(args.escape)

            if args.telnet_server:
                addr, _, port = args.telnet_server.partition(':')
                nport = 0
                try:
                    nport = int(port)
                except ValueError:
                    pass
                if addr == '' or nport == 0:
                    raise ConfigError('format for --telnet-server must be '
                                      'ADDR:PORT (like 127.0.0.1:20000)')

            while not stop_event.is_set():
                epoll = select.epoll()
                try:
                    if args.telnet_server:
                        with TelnetServer(addr, nport, stop_event) as console:
                            # We loop inside the Telnet server otherwise the client is disconnected when user use the reload command inside a terminal
                            while not stop_event.is_set():
                                try:
                                    with IOU(ttyC, ttyS, stop_event) as router:
                                        send_recv_loop(epoll, console, router, b'', stop_event)
                                except ConnectionRefusedError:
                                    pass
                    else:
                        with IOU(ttyC, ttyS, stop_event) as router, TTY() as console:
                            send_recv_loop(epoll, console, router, esc_char, stop_event)
                except ConnectionRefusedError:
                    pass
                except KeyboardInterrupt:
                    sys.exit(EXIT_ABORT)
                finally:
                    # Put us at the beginning of a line
                    if not args.telnet_server:
                        print()

    except IOUConError as e:
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        else:
            log.error("ioucon: {}".format(e))
        sys.exit(EXIT_FAILURE)

    log.info("exiting...")


def main():

    import threading
    stop_event = threading.Event()
    args = get_args()
    start_ioucon(args, stop_event)

if __name__ == '__main__':
    main()
