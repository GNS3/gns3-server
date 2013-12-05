# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

"""
STOMP frame representation, decoding and encoding
http://stomp.github.io/stomp-specification-1.2.html
Adapted from Jason R. Briggs's code
https://github.com/jasonrbriggs/stomp.py
"""

import re
from .utils import encode


class Frame(object):
    """
    A STOMP frame. Comprises a command, the headers and the body content.
    """

    # Used to parse STOMP header lines in the format "key:value",
    HEADER_LINE_RE = re.compile('(?P<key>[^:]+)[:](?P<value>.*)')
    # As of STOMP 1.2, lines can end with either line feed, or carriage return plus line feed.
    PREAMBLE_END_RE = re.compile('\n\n|\r\n\r\n')
    # As of STOMP 1.2, lines can end with either line feed, or carriage return plus line feed.
    LINE_END_RE = re.compile('\n|\r\n')
    # NULL value
    NULL = b'\x00'

    def __init__(self, cmd=None, headers={}, body=None):
        self._cmd = cmd
        self._headers = headers
        self._body = body

    @property
    def cmd(self):

        return(self._cmd)

    @cmd.setter
    def cmd(self, cmd):

        self._cmd = cmd

    @property
    def headers(self):

        return(self._headers)

    @headers.setter
    def headers(self, headers):

        self._headers = headers

    @property
    def body(self):

        return(self._body)

    @body.setter
    def body(self, body):

        self._body = body

    def encode(self):
        """
        Encodes this frame to be send on the wire
        """

        lines = []
        if self._cmd:
            lines.append(self._cmd)
            lines.append("\n")
        for key, vals in sorted(self._headers.items()):
            if type(vals) != tuple:
                vals = (vals,)
            for val in vals:
                lines.append("%s:%s\n" % (key, val))
        lines.append("\n")
        if self._body:
            lines.append(self._body)

        if self._cmd:
            lines.append(self.NULL)

        encoded_lines = (encode(line) for line in lines)
        return b''.join(encoded_lines)

    @classmethod
    def parse_headers(cls, lines, offset=0):
        """
        Parses frame headers

        :param lines: Frame preamble lines
        :param offset: To start parsing at the given offset
        :returns: Headers in dict header:value
        """

        headers = {}
        for header_line in lines[offset:]:
            header_match = cls.HEADER_LINE_RE.match(header_line)
            if header_match:
                key = header_match.group('key')
                if key not in headers:
                    headers[key] = header_match.group('value')
        return headers

    @classmethod
    def parse_frame(cls, frame):
        """
        Parses a frame

        :params frame: The frame data to be parsed
        :returns: STOMP Frame object
        """

        f = Frame()
        # End-of-line (EOL) indicates an heart beat frame
        if frame == '\x0a':
            f.cmd = 'heartbeat'  # This will have the frame ignored
            return f

        mat = cls.PREAMBLE_END_RE.search(frame)
        preamble_end = -1
        if mat:
            preamble_end = mat.start()
        if preamble_end == -1:
            preamble_end = len(frame)
        preamble = frame[0:preamble_end]
        preamble_lines = cls.LINE_END_RE.split(preamble)
        f.body = frame[preamble_end + 2:]
        if f.body[-1] == '\x00':
            f.body = f.body[:-1]

        # Skip any leading newlines
        first_line = 0
        while first_line < len(preamble_lines) and len(preamble_lines[first_line]) == 0:
            first_line += 1

        # Extract frame type/command
        f.cmd = preamble_lines[first_line]

        # Put headers into a key/value map
        f.headers = cls.parse_headers(preamble_lines, first_line + 1)

        return f
