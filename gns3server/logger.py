#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

"""Provide a pretty logging on console"""


import logging
import sys
import os
import shutil
import gzip

from logging.handlers import RotatingFileHandler


class ColouredFormatter(logging.Formatter):
    RESET = '\x1B[0m'
    RED = '\x1B[31m'
    YELLOW = '\x1B[33m'
    GREEN = '\x1B[32m'
    PINK = '\x1b[35m'

    def format(self, record, colour=False):

        message = super().format(record)

        if not colour or sys.platform.startswith("win"):
            return message.replace("#RESET#", "")

        level_no = record.levelno
        if level_no >= logging.CRITICAL:
            colour = self.RED
        elif level_no >= logging.ERROR:
            colour = self.RED
        elif level_no >= logging.WARNING:
            colour = self.YELLOW
        elif level_no >= logging.INFO:
            colour = self.GREEN
        elif level_no >= logging.DEBUG:
            colour = self.PINK
        else:
            colour = self.RESET

        message = message.replace("#RESET#", self.RESET)
        message = '{colour}{message}{reset}'.format(colour=colour, message=message, reset=self.RESET)

        return message


class ColouredStreamHandler(logging.StreamHandler):

    def format(self, record, colour=False):

        if not isinstance(self.formatter, ColouredFormatter):
            self.formatter = ColouredFormatter()

        return self.formatter.format(record, colour)

    def emit(self, record):

        stream = self.stream
        try:
            msg = self.format(record, stream.isatty())
            stream.write(msg)
            stream.write(self.terminator)
            self.flush()
        # On OSX when frozen flush raise a BrokenPipeError
        except BrokenPipeError:
            pass
        except Exception:
            self.handleError(record)


class WinStreamHandler(logging.StreamHandler):

    def emit(self, record):

        if sys.stdin.encoding != "utf-8":
            record = record

        stream = self.stream
        try:
            msg = self.formatter.format(record, stream.isatty())
            stream.write(msg.encode(stream.encoding, errors="replace").decode(stream.encoding))
            stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


class LogFilter:
    """
    This filter some noise from the logs
    """
    def filter(record):
        if record.name == "aiohttp.access" and "/settings" in record.msg and "200" in record.msg:
            return 0
        return 1


class CompressedRotatingFileHandler(RotatingFileHandler):
    """
    Custom rotating file handler with compression support.
    """

    def doRollover(self):
        if self.stream:
            self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d.gz" % (self.baseFilename, i)
                dfn = "%s.%d.gz" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1.gz"
            if os.path.exists(dfn):
                os.remove(dfn)
            with open(self.baseFilename, 'rb') as f_in, gzip.open(dfn, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        self.mode = 'w'
        self.stream = self._open()


def init_logger(level, logfile=None, max_bytes=10000000, backup_count=10, compression=True, quiet=False):
    if logfile and len(logfile) > 0:
        if compression:
            stream_handler = CompressedRotatingFileHandler(logfile, maxBytes=max_bytes, backupCount=backup_count)
        else:
            stream_handler = RotatingFileHandler(logfile, maxBytes=max_bytes, backupCount=backup_count)
        stream_handler.formatter = ColouredFormatter("{asctime} {levelname} {filename}:{lineno} {message}", "%Y-%m-%d %H:%M:%S", "{")
    elif sys.platform.startswith("win"):
        stream_handler = WinStreamHandler(sys.stdout)
        stream_handler.formatter = ColouredFormatter("{asctime} {levelname} {filename}:{lineno} {message}", "%Y-%m-%d %H:%M:%S", "{")
    else:
        stream_handler = ColouredStreamHandler(sys.stdout)
        stream_handler.formatter = ColouredFormatter("{asctime} {levelname} {filename}:{lineno}#RESET# {message}", "%Y-%m-%d %H:%M:%S", "{")
    if quiet:
        stream_handler.addFilter(logging.Filter(name="user_facing"))
        logging.getLogger('user_facing').propagate = False
    if level > logging.DEBUG:
        stream_handler.addFilter(LogFilter)
    logging.basicConfig(level=level, handlers=[stream_handler])
    return logging.getLogger('user_facing')
