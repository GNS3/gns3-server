# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

# TODO: port TelnetServer to asyncio

import sys
import time
import threading
import socket
import select

import logging
log = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    import win32pipe
    import win32file


class TelnetServer(threading.Thread):

    """
    Mini Telnet Server.

    :param vm_name: Virtual machine name
    :param pipe_path: path to VM pipe (UNIX socket on Linux/UNIX, Named Pipe on Windows)
    :param host: server host
    :param port: server port
    """

    def __init__(self, vm_name, pipe_path, host, port):

        threading.Thread.__init__(self)
        self._vm_name = vm_name
        self._pipe = pipe_path
        self._host = host
        self._port = port
        self._reader_thread = None
        self._use_thread = False
        self._write_lock = threading.Lock()
        self._clients = {}
        self._timeout = 1
        self._alive = True

        if sys.platform.startswith("win"):
            # we must a thread for reading the pipe on Windows because it is a Named Pipe and it cannot be monitored by select()
            self._use_thread = True

        for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
            af, socktype, proto, _, sa = res
            self._server_socket = socket.socket(af, socktype, proto)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(sa)
            self._server_socket.listen(socket.SOMAXCONN)
            break

        log.info("Telnet server initialized, waiting for clients on {}:{}".format(self._host, self._port))

    def run(self):
        """
        Thread loop.
        """

        while True:

            recv_list = [self._server_socket.fileno()]

            if not self._use_thread:
                recv_list.append(self._pipe.fileno())

            for client in self._clients.values():
                if client.is_active():
                    recv_list.append(client.socket().fileno())
                else:
                    del self._clients[client.socket().fileno()]
                    try:
                        client.socket().shutdown(socket.SHUT_RDWR)
                    except OSError as e:
                        log.warn("shutdown: {}".format(e))
                    client.socket().close()
                    break

            try:
                rlist, slist, elist = select.select(recv_list, [], [], self._timeout)
            except OSError as e:
                log.critical("fatal select error: {}".format(e))
                return False

            if not self._alive:
                log.info("Telnet server for {} is exiting".format(self._vm_name))
                return True

            for sock_fileno in rlist:
                if sock_fileno == self._server_socket.fileno():

                    try:
                        sock, addr = self._server_socket.accept()
                        host, port = addr
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        log.info("new client {}:{} has connected".format(host, port))
                    except OSError as e:
                        log.error("could not accept new client: {}".format(e))
                        continue

                    new_client = TelnetClient(self._vm_name, sock, host, port)
                    self._clients[sock.fileno()] = new_client

                    if self._use_thread and not self._reader_thread:
                        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
                        self._reader_thread.start()

                elif not self._use_thread and sock_fileno == self._pipe.fileno():

                    data = self._read_from_pipe()
                    if not data:
                        log.warning("pipe has been closed!")
                        return False
                    for client in self._clients.values():
                        try:
                            client.send(data)
                        except OSError as e:
                            log.debug(e)
                            client.deactivate()

                elif sock_fileno in self._clients:
                    try:
                        data = self._clients[sock_fileno].socket_recv()

                        if not data:
                            continue

                        # For some reason, windows likes to send "cr/lf" when you send a "cr".
                        # Strip that so we don't get a double prompt.
                        data = data.replace(b"\r\n", b"\n")

                        self._write_to_pipe(data)
                    except Exception as msg:
                        log.info(msg)
                        self._clients[sock_fileno].deactivate()

    def _write_to_pipe(self, data):
        """
        Writes data to the pipe.

        :param data: data to write
        """

        if sys.platform.startswith('win'):
            win32file.WriteFile(self._pipe, data)
        else:
            self._pipe.sendall(data)

    def _read_from_pipe(self):
        """
        Reads data from the pipe.

        :returns: data
        """

        if sys.platform.startswith('win'):
            (read, num_avail, num_message) = win32pipe.PeekNamedPipe(self._pipe, 0)
            if num_avail > 0:
                (error_code, output) = win32file.ReadFile(self._pipe, num_avail, None)
                return output
            return b""
        else:
            return self._pipe.recv(1024)

    def _reader(self):
        """
        Loops forever and copy everything from the pipe to the socket.
        """

        log.debug("reader thread has started")
        while self._alive:
            try:
                data = self._read_from_pipe()
                if not data and not sys.platform.startswith('win'):
                    log.debug("pipe has been closed! (no data)")
                    break
                self._write_lock.acquire()
                try:
                    for client in self._clients.values():
                        client.send(data)
                finally:
                    self._write_lock.release()
                if sys.platform.startswith('win'):
                    # sleep every 10 ms
                    time.sleep(0.01)
            except Exception as e:
                log.debug("pipe has been closed! {}".format(e))
                break
        log.debug("reader thread exited")
        self.stop()

    def stop(self):
        """
        Stops the server.
        """

        if self._alive:
            self._alive = False

        for client in self._clients.values():
            client.socket().close()
            client.deactivate()

# Mostly from https://code.google.com/p/miniboa/source/browse/trunk/miniboa/telnet.py

# Telnet Commands
SE = 240    # End of sub-negotiation parameters
NOP = 241    # No operation
DATMK = 242    # Data stream portion of a sync.
BREAK = 243    # NVT Character BRK
IP = 244    # Interrupt Process
AO = 245    # Abort Output
AYT = 246    # Are you there
EC = 247    # Erase Character
EL = 248    # Erase Line
GA = 249    # The Go Ahead Signal
SB = 250    # Sub-option to follow
WILL = 251    # Will; request or confirm option begin
WONT = 252    # Wont; deny option request
DO = 253    # Do = Request or confirm remote option
DONT = 254    # Don't = Demand or confirm option halt
IAC = 255    # Interpret as Command
SEND = 1      # Sub-process negotiation SEND command
IS = 0      # Sub-process negotiation IS command

# Telnet Options
BINARY = 0      # Transmit Binary
ECHO = 1      # Echo characters back to sender
RECON = 2      # Reconnection
SGA = 3      # Suppress Go-Ahead
TMARK = 6      # Timing Mark
TTYPE = 24     # Terminal Type
NAWS = 31     # Negotiate About Window Size
LINEMO = 34     # Line Mode


class TelnetClient(object):

    """
    Represents a Telnet client connection.

    :param vm_name: VM name
    :param sock: socket connection
    :param host: IP of the Telnet client
    :param port: port of the Telnet client
    """

    def __init__(self, vm_name, sock, host, port):

        self._active = True
        self._sock = sock
        self._host = host
        self._port = port

        sock.send(bytes([IAC, WILL, ECHO,
                         IAC, WILL, SGA,
                         IAC, WILL, BINARY,
                         IAC, DO, BINARY]))

        welcome_msg = "{} console is now available... Press RETURN to get started.\r\n".format(vm_name)
        sock.send(welcome_msg.encode('utf-8'))

    def is_active(self):
        """
        Returns either the client is active or not.

        :return: boolean
        """

        return self._active

    def socket(self):
        """
        Returns the socket for this Telnet client.

        :returns: socket instance.
        """

        return self._sock

    def send(self, data):
        """
        Sends data to the remote end.

        :param data: data to send
        """

        try:
            self._sock.send(data)
        except OSError as e:
            self._active = False
            raise Exception("Socket send: {}".format(e))

    def deactivate(self):
        """
        Sets the client to disconnect on the next server poll.
        """

        self._active = False

    def socket_recv(self):
        """
        Called by Telnet Server when data is ready.
        """

        try:
            buf = self._sock.recv(1024)
        except BlockingIOError:
            return None
        except ConnectionResetError:
            buf = b''

        # is the connection closed?
        if not buf:
            raise Exception("connection closed by {}:{}".format(self._host, self._port))

        # Process and remove any telnet commands from the buffer
        if IAC in buf:
            buf = self._IAC_parser(buf)

        return buf

    def _read_block(self, bufsize):
        """
        Reads a block for data from the socket.

        :param bufsize: size of the buffer
        :returns: data read
        """
        buf = self._sock.recv(1024, socket.MSG_WAITALL)
        # If we don't get everything we were looking for then the
        # client probably disconnected.
        if len(buf) < bufsize:
            raise Exception("connection closed by {}:{}".format(self._host, self._port))
        return buf

    def _IAC_parser(self, buf):
        """
        Processes and removes any Telnet commands from the buffer.

        :param buf: buffer
        :returns: buffer minus Telnet commands
        """

        skip_to = 0
        while self._active:
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
                    self._sock.send(b'\r\nYour Are-You-There received. I am here.\r\n')
                elif iac_cmd[1] == IAC:
                    # It's data, not an IAC
                    iac_cmd.pop()
                    # This prevents the 0xff from being
                    # interrupted as yet another IAC
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
                if iac_cmd[1] == DO and iac_cmd[2] not in [ECHO, SGA, BINARY]:
                    self._sock.send(bytes([IAC, WONT, iac_cmd[2]]))
                    log.debug("Telnet WON'T {:#x}".format(iac_cmd[2]))
                else:
                    log.debug("Unhandled telnet command: "
                              "{0:#x} {1:#x} {2:#x}".format(*iac_cmd))

            # Remove the entire TELNET command from the buffer
            buf = buf.replace(iac_cmd, b'', 1)

        # Return the new copy of the buffer, minus telnet commands
        return buf

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    if sys.platform.startswith('win'):
        import msvcrt
        pipe_name = r'\\.\pipe\VBOX\Linux_Microcore_4.7.1'
        pipe = open(pipe_name, 'a+b')
        telnet_server = TelnetServer("VBOX", msvcrt.get_osfhandle(pipe.fileno()), "127.0.0.1", 3900)
    else:
        pipe_name = "/tmp/pipe_test"
        try:
            unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            unix_socket.connect(pipe_name)
        except OSError as e:
            print("Could not connect to UNIX socket {}: {}".format(pipe_name, e))
            sys.exit(False)
        telnet_server = TelnetServer("VBOX", unix_socket, "127.0.0.1", 3900)

    telnet_server.setDaemon(True)
    telnet_server.start()
    try:
        telnet_server.join()
    except KeyboardInterrupt:
        telnet_server.stop()
        telnet_server.join(timeout=3)
