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

# Parts of this code have been taken from Pyserial project (http://pyserial.sourceforge.net/) under Python license

import sys
import time
import threading
import socket
import select

if sys.platform.startswith("win"):
    import win32pipe
    import win32file


class PipeProxy(threading.Thread):

    def __init__(self, name, pipe, host, port):
        self.devname = name
        self.pipe = pipe
        self.host = host
        self.port = port
        self.server = None
        self.reader_thread = None
        self.use_thread = False
        self._write_lock = threading.Lock()
        self.clients = {}
        self.timeout = 0.1
        self.alive = True

        if sys.platform.startswith("win"):
            # we must a thread for reading the pipe on Windows because it is a Named Pipe and it cannot be monitored by select()
            self.use_thread = True

        try:
            if self.host.__contains__(':'):
                # IPv6 address support
                self.server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            else:
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server.bind((self.host, int(self.port)))
                self.server.listen(5)
        except socket.error as msg:
            self.error("unable to create the socket server %s" % msg)
            return

        threading.Thread.__init__(self)
        self.debug("initialized, waiting for clients on %s:%i..." % (self.host, self.port))

    def error(self, msg):

        sys.stderr.write("ERROR -> %s PIPE PROXY: %s\n" % (self.devname, msg))

    def debug(self, msg):

        sys.stdout.write("INFO -> %s PIPE PROXY: %s\n" % (self.devname, msg))

    def run(self):

        while True:

            recv_list = [self.server.fileno()]

            if not self.use_thread:
                recv_list.append(self.pipe.fileno())

            for client in self.clients.values():
                if client.active:
                    recv_list.append(client.fileno)
                else:
                    self.debug("lost client %s" % client.addrport())
                    try:
                        client.sock.close()
                    except:
                        pass
                    del self.clients[client.fileno]

            try:
                rlist, slist, elist = select.select(recv_list, [], [], self.timeout)
            except select.error as err:
                self.error("fatal select error %d:%s" % (err[0], err[1]))
                return False

            if not self.alive:
                self.debug('Exiting ...')
                return True

            for sock_fileno in rlist:
                if sock_fileno == self.server.fileno():

                    try:
                        sock, addr = self.server.accept()
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        self.debug("new client %s:%s" % (addr[0], addr[1]))
                    except socket.error as err:
                        self.error("accept error %d:%s" % (err[0], err[1]))
                        continue

                    new_client = TelnetClient(sock, addr)
                    self.clients[new_client.fileno] = new_client
                    welcome_msg = "%s console is now available ... Press RETURN to get started.\r\n" % self.devname
                    sock.send(welcome_msg.encode('utf-8'))

                    if self.use_thread and not self.reader_thread:
                        self.reader_thread = threading.Thread(target=self.reader)
                        self.reader_thread.setDaemon(True)
                        self.reader_thread.setName('pipe->socket')
                        self.reader_thread.start()

                elif not self.use_thread and sock_fileno == self.pipe.fileno():

                    data = self.read_from_pipe()
                    if not data:
                        self.debug("pipe has been closed!")
                        return False
                    for client in self.clients.values():
                        try:
                            client.send(data)
                        except:
                            self.debug(msg)
                            client.deactivate()
                elif sock_fileno in self.clients:
                    try:
                        data = self.clients[sock_fileno].socket_recv()

                        # For some reason, windows likes to send "cr/lf" when you send a "cr".
                        # Strip that so we don't get a double prompt.
                        data = data.replace(b"\r\n", b"\n")

                        self.write_to_pipe(data)
                    except Exception as msg:
                        self.debug(msg)
                        self.clients[sock_fileno].deactivate()

    def write_to_pipe(self, data):

        if sys.platform.startswith('win'):
            win32file.WriteFile(self.pipe, data)
        else:
            self.pipe.sendall(data)

    def read_from_pipe(self):

        if sys.platform.startswith('win'):
            (read, num_avail, num_message) = win32pipe.PeekNamedPipe(self.pipe, 0)
            if num_avail > 0:
                (error_code, output) = win32file.ReadFile(self.pipe, num_avail, None)
                return output
            return ""
        else:
            return self.pipe.recv(1024)

    def reader(self):
        """loop forever and copy pipe->socket"""

        self.debug("reader thread started")
        while self.alive:
            try:
                data = self.read_from_pipe()
                if not data and not sys.platform.startswith('win'):
                    self.debug("pipe has been closed!")
                    break
                self._write_lock.acquire()
                try:
                    for client in self.clients.values():
                        client.send(data)
                finally:
                    self._write_lock.release()
                if sys.platform.startswith('win'):
                    # sleep every 10 ms
                    time.sleep(0.01)
            except:
                self.debug("pipe has been closed!")
                break
        self.debug("reader thread exited")
        self.stop()

    def stop(self):
        """Stop copying"""

        if self.alive:
            self.alive = False
        for client in self.clients.values():
            client.sock.close()
            client.deactivate()

# telnet protocol characters
IAC  = 255 # Interpret As Command
DONT = 254
DO   = 253
WONT = 252
WILL = 251
IAC_DOUBLED = [IAC, IAC]

SE  = 240  # Subnegotiation End
NOP = 241  # No Operation
DM  = 242  # Data Mark
BRK = 243  # Break
IP  = 244  # Interrupt process
AO  = 245  # Abort output
AYT = 246  # Are You There
EC  = 247  # Erase Character
EL  = 248  # Erase Line
GA  = 249  # Go Ahead
SB =  250  # Subnegotiation Begin

# selected telnet options
ECHO = 1   # echo
SGA = 3    # suppress go ahead
LINEMODE = 34 # line mode
TERMTYPE = 24 # terminal type

# Telnet filter states
M_NORMAL = 0
M_IAC_SEEN = 1
M_NEGOTIATE = 2

# TelnetOption and TelnetSubnegotiation states
REQUESTED = 'REQUESTED'
ACTIVE = 'ACTIVE'
INACTIVE = 'INACTIVE'
REALLY_INACTIVE = 'REALLY_INACTIVE'

class TelnetOption(object):
    """Manage a single telnet option, keeps track of DO/DONT WILL/WONT."""

    def __init__(self, connection, name, option, send_yes, send_no, ack_yes, ack_no, initial_state, activation_callback=None):
        """Init option.
        :param connection: connection used to transmit answers
        :param name: a readable name for debug outputs
        :param send_yes: what to send when option is to be enabled.
        :param send_no: what to send when option is to be disabled.
        :param ack_yes: what to expect when remote agrees on option.
        :param ack_no: what to expect when remote disagrees on option.
        :param initial_state: options initialized with REQUESTED are tried to
            be enabled on startup. use INACTIVE for all others.
        """
        self.connection = connection
        self.name = name
        self.option = option
        self.send_yes = send_yes
        self.send_no = send_no
        self.ack_yes = ack_yes
        self.ack_no = ack_no
        self.state = initial_state
        self.active = False
        self.activation_callback = activation_callback

    def __repr__(self):
        """String for debug outputs"""
        return "%s:%s(%s)" % (self.name, self.active, self.state)

    def process_incoming(self, command):
        """A DO/DONT/WILL/WONT was received for this option, update state and
        answer when needed."""
        if command == self.ack_yes:
            if self.state is REQUESTED:
                self.state = ACTIVE
                self.active = True
                if self.activation_callback is not None:
                    self.activation_callback()
            elif self.state is ACTIVE:
                pass
            elif self.state is INACTIVE:
                self.state = ACTIVE
                self.connection.telnetSendOption(self.send_yes, self.option)
                self.active = True
                if self.activation_callback is not None:
                    self.activation_callback()
            elif self.state is REALLY_INACTIVE:
                self.connection.telnetSendOption(self.send_no, self.option)
            else:
                raise ValueError('option in illegal state %r' % self)
        elif command == self.ack_no:
            if self.state is REQUESTED:
                self.state = INACTIVE
                self.active = False
            elif self.state is ACTIVE:
                self.state = INACTIVE
                self.connection.telnetSendOption(self.send_no, self.option)
                self.active = False
            elif self.state is INACTIVE:
                pass
            elif self.state is REALLY_INACTIVE:
                pass
            else:
                raise ValueError('option in illegal state %r' % self)

class TelnetClient(object):

    """
    Represents a client connection via Telnet.

    First argument is the socket discovered by the Telnet Server.
    Second argument is the tuple (ip address, port number).
    """

    def __init__(self, sock, addr_tup):
        self.active = True          # Turns False when the connection is lost
        self.sock = sock            # The connection's socket
        self.fileno = sock.fileno() # The socket's file descriptor
        self.address = addr_tup[0]  # The client's remote TCP/IP address
        self.port = addr_tup[1]     # The client's remote port

        # filter state machine
        self.mode = M_NORMAL
        self.suboption = None
        self.telnet_command = None

        # all supported telnet options
        self._telnet_options = [
            TelnetOption(self, 'ECHO', ECHO, WILL, WONT, DO, DONT, REQUESTED),
            TelnetOption(self, 'we-SGA', SGA, WILL, WONT, DO, DONT, REQUESTED),
            TelnetOption(self, 'they-SGA', SGA, DO, DONT, WILL, WONT, INACTIVE),
            TelnetOption(self, 'LINEMODE', LINEMODE, DONT, DONT, WILL, WONT, REQUESTED),
            TelnetOption(self, 'TERMTYPE', TERMTYPE, DO, DONT, WILL, WONT, REQUESTED),
            ]

        for option in self._telnet_options:
            if option.state is REQUESTED:
                self.telnetSendOption(option.send_yes, option.option)

    def telnetSendOption(self, action, option):
        """Send DO, DONT, WILL, WONT."""
        self.sock.sendall(bytes([IAC, action, option]))

    def escape(self, data):
        """ All outgoing data has to be properly escaped, so that no IAC character 
        in the data stream messes up the Telnet state machine in the server.
        """
        for byte in data:
            if byte == IAC:
                yield IAC
                yield IAC
            else:
                yield byte

    def filter(self, data):
        """ handle a bunch of incoming bytes. this is a generator. it will yield
        all characters not of interest for Telnet
        """
        for byte in data:
            if self.mode == M_NORMAL:
                # interpret as command or as data
                if byte == IAC:
                    self.mode = M_IAC_SEEN
                else:
                    # store data in sub option buffer or pass it to our
                    # consumer depending on state
                    if self.suboption is not None:
                        self.suboption.append(byte)
                    else:
                        yield byte
            elif self.mode == M_IAC_SEEN:
                if byte == IAC:
                    # interpret as command doubled -> insert character
                    # itself
                    if self.suboption is not None:
                        self.suboption.append(byte)
                    else:
                        yield byte
                    self.mode = M_NORMAL
                elif byte == SB:
                    # sub option start
                    self.suboption = bytearray()
                    self.mode = M_NORMAL
                elif byte == SE:
                    # sub option end -> process it now
                    #self._telnetProcessSubnegotiation(bytes(self.suboption))
                    self.suboption = None
                    self.mode = M_NORMAL
                elif byte in (DO, DONT, WILL, WONT):
                    # negotiation
                    self.telnet_command = byte
                    self.mode = M_NEGOTIATE
                else:
                    # other telnet commands are ignored!
                    self.mode = M_NORMAL
            elif self.mode == M_NEGOTIATE: # DO, DONT, WILL, WONT was received, option now following
                self._telnetNegotiateOption(self.telnet_command, byte)
                self.mode = M_NORMAL

    def _telnetNegotiateOption(self, command, option):
        """Process incoming DO, DONT, WILL, WONT."""
        # check our registered telnet options and forward command to them
        # they know themselves if they have to answer or not
        known = False
        for item in self._telnet_options:
            # can have more than one match! as some options are duplicated for
            # 'us' and 'them'
            if item.option == option:
                item.process_incoming(command)
                known = True
        if not known:
            # handle unknown options
            # only answer to positive requests and deny them
            if command == WILL or command == DO:
                self.telnetSendOption((command == WILL and DONT or WONT), option)

    def send(self, data):
        """
        Send data to the distant end.
        """

        try:
            self.sock.sendall(bytes(self.escape(data)))
        except socket.error as ex:
            self.active = False
            raise Exception("socket.sendall() error '%d:%s' from %s" % (ex[0], ex[1], self.addrport()))

    def deactivate(self):
        """
        Set the client to disconnect on the next server poll.
        """
        self.active = False

    def addrport(self):
        """
        Return the DE's IP address and port number as a string.
        """
        return "%s:%s" % (self.address, self.port)

    def socket_recv(self):
        """
        Called by TelnetServer when recv data is ready.
        """
        try:
            data = self.sock.recv(4096)
        except socket.error as ex:
            raise Exception("socket.recv() error '%d:%s' from %s" % (ex[0], ex[1], self.addrport()))

        ## Did they close the connection?
        size = len(data)
        if size == 0:
            raise Exception("connection closed by %s" % self.addrport())

        return bytes(self.filter(data))

if __name__ == '__main__':

    if sys.platform.startswith('win'):
        import msvcrt
        pipe_name = r'\\.\pipe\VBOX\Linux_Microcore_3.8.2'
        pipe = open(pipe_name, 'a+b')
        pipe_proxy = PipeProxy("VBOX", msvcrt.get_osfhandle(pipe.fileno()), '127.0.0.1', 3900)
    else:
        try:
            unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            #unix_socket.settimeout(0.1)
            unix_socket.connect("/tmp/pipe_test")
        except socket.error as err:
            print("Socket error -> %d:%s" % (err[0], err[1]))
            sys.exit(False)
        pipe_proxy = PipeProxy('VBOX', unix_socket, '127.0.0.1', 3900)

    pipe_proxy.setDaemon(True)
    pipe_proxy.start()
    pipe.proxy.stop()
    pipe_proxy.join()
