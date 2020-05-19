#!/usr/bin/env python
#
# Copyright (C) 2019 GNS3 Technologies Inc.
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
Iterable ZIP archive generator.

Derived directly from zipfile.py and the zipstream project
https://github.com/allanlei/python-zipstream
"""

import os
import sys
import stat
import struct
import time
import zipfile
import asyncio
import aiofiles
from concurrent import futures

from zipfile import (structCentralDir, structEndArchive64, structEndArchive, structEndArchive64Locator,
                     stringCentralDir, stringEndArchive64, stringEndArchive, stringEndArchive64Locator)

stringDataDescriptor = b'PK\x07\x08'  # magic number for data descriptor


def _get_compressor(compress_type):
    """
    Return the compressor.
    """

    if compress_type == zipfile.ZIP_DEFLATED:
        from zipfile import zlib
        return zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
    elif compress_type == zipfile.ZIP_BZIP2:
        from zipfile import bz2
        return bz2.BZ2Compressor()
    elif compress_type == zipfile.ZIP_LZMA:
        from zipfile import LZMACompressor
        return LZMACompressor()
    else:
        return None


class PointerIO(object):

    def __init__(self, mode='wb'):
        if mode not in ('wb', ):
            raise RuntimeError('zipstream.ZipFile() requires mode "wb"')
        self.data_pointer = 0
        self.__mode = mode
        self.__closed = False

    @property
    def mode(self):
        return self.__mode

    @property
    def closed(self):
        return self.__closed

    def close(self):
        self.__closed = True

    def flush(self):
        pass

    def next(self):
        raise NotImplementedError()

    def tell(self):
        return self.data_pointer

    def truncate(size=None):
        raise NotImplementedError()

    def write(self, data):
        if self.closed:
            raise ValueError('I/O operation on closed file')

        if isinstance(data, str):
            data = data.encode('utf-8')
        if not isinstance(data, bytes):
            raise TypeError('expected bytes')
        self.data_pointer += len(data)
        return data


class ZipInfo(zipfile.ZipInfo):

    def __init__(self, *args, **kwargs):
        zipfile.ZipInfo.__init__(self, *args, **kwargs)

    def DataDescriptor(self):
        """
        crc-32                          4 bytes
        compressed size                 4 bytes
        uncompressed size               4 bytes
        """

        if self.compress_size > zipfile.ZIP64_LIMIT or self.file_size > zipfile.ZIP64_LIMIT:
            fmt = b'<4sLQQ'
        else:
            fmt = b'<4sLLL'
        return struct.pack(fmt, stringDataDescriptor, self.CRC, self.compress_size, self.file_size)


class ZipFile(zipfile.ZipFile):

    def __init__(self, fileobj=None, mode='w', compression=zipfile.ZIP_STORED, allowZip64=True, chunksize=32768):
        """Open the ZIP file with mode write "w"."""

        if mode not in ('w', ):
            raise RuntimeError('aiozipstream.ZipFile() requires mode "w"')
        if fileobj is None:
            fileobj = PointerIO()

        self._comment = b''
        zipfile.ZipFile.__init__(self, fileobj, mode=mode, compression=compression, allowZip64=allowZip64)
        self._chunksize = chunksize
        self.paths_to_write = []

    def __aiter__(self):
        return self._stream()

    @property
    def comment(self):
        """
        The comment text associated with the ZIP file.
        """

        return self._comment

    @comment.setter
    def comment(self, comment):
        """
        Add a comment text associated with the ZIP file.
        """

        if not isinstance(comment, bytes):
            raise TypeError("comment: expected bytes, got %s" % type(comment))
        # check for valid comment length
        if len(comment) >= zipfile.ZIP_MAX_COMMENT:
            if self.debug:
                print('Archive comment is too long; truncating to %d bytes' % zipfile.ZIP_MAX_COMMENT)
            comment = comment[:zipfile.ZIP_MAX_COMMENT]
        self._comment = comment
        self._didModify = True

    async def data_generator(self, path):

        async with aiofiles.open(path, "rb") as f:
            while True:
                part = await f.read(self._chunksize)
                if not part:
                    break
                yield part
        return

    async def _run_in_executor(self, task, *args, **kwargs):
        """
        Run synchronous task in separate thread and await for result.
        """

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(futures.ThreadPoolExecutor(max_workers=1), task, *args, **kwargs)

    async def _stream(self):

        for kwargs in self.paths_to_write:
            async for chunk in self._write(**kwargs):
                yield chunk
        for chunk in self._close():
            yield chunk

    def write(self, filename, arcname=None, compress_type=None):
        """
        Write a file to the archive under the name `arcname`.
        """

        kwargs = {'filename': filename, 'arcname': arcname, 'compress_type': compress_type}
        self.paths_to_write.append(kwargs)

    def write_iter(self, arcname, iterable, compress_type=None):
        """
        Write the bytes iterable `iterable` to the archive under the name `arcname`.
        """

        kwargs = {'arcname': arcname, 'iterable': iterable, 'compress_type': compress_type}
        self.paths_to_write.append(kwargs)

    def writestr(self, arcname, data, compress_type=None):
        """
        Writes a str into ZipFile by wrapping data as a generator
        """

        def _iterable():
            yield data
        return self.write_iter(arcname, _iterable(), compress_type=compress_type)

    async def _write(self, filename=None, iterable=None, arcname=None, compress_type=None):
        """
        Put the bytes from filename into the archive under the name `arcname`.
        """

        if not self.fp:
            raise RuntimeError(
                  "Attempt to write to ZIP archive that was already closed")
        if (filename is None and iterable is None) or (filename is not None and iterable is not None):
            raise ValueError("either (exclusively) filename or iterable shall be not None")

        if filename:
            st = os.stat(filename)
            isdir = stat.S_ISDIR(st.st_mode)
            mtime = time.localtime(st.st_mtime)
            date_time = mtime[0:6]
        else:
            st, isdir, date_time = None, False, time.localtime()[0:6]
        # Create ZipInfo instance to store file information
        if arcname is None:
            arcname = filename
        arcname = os.path.normpath(os.path.splitdrive(arcname)[1])
        while arcname[0] in (os.sep, os.altsep):
            arcname = arcname[1:]
        if isdir:
            arcname += '/'
        zinfo = ZipInfo(arcname, date_time)
        if st:
            zinfo.external_attr = (st[0] & 0xFFFF) << 16      # Unix attributes
        else:
            zinfo.external_attr = 0o600 << 16     # ?rw-------
        if compress_type is None:
            zinfo.compress_type = self.compression
        else:
            zinfo.compress_type = compress_type

        if st:
            zinfo.file_size = st[6]
        else:
            zinfo.file_size = 0
        zinfo.flag_bits = 0x00
        zinfo.flag_bits |= 0x08                 # ZIP flag bits, bit 3 indicates presence of data descriptor
        zinfo.header_offset = self.fp.tell()    # Start of header bytes
        if zinfo.compress_type == zipfile.ZIP_LZMA:
            # Compressed data includes an end-of-stream (EOS) marker
            zinfo.flag_bits |= 0x02

        self._writecheck(zinfo)
        self._didModify = True

        if isdir:
            zinfo.file_size = 0
            zinfo.compress_size = 0
            zinfo.CRC = 0
            self.filelist.append(zinfo)
            self.NameToInfo[zinfo.filename] = zinfo
            yield self.fp.write(zinfo.FileHeader(False))
            return

        cmpr = _get_compressor(zinfo.compress_type)

        # Must overwrite CRC and sizes with correct data later
        zinfo.CRC = CRC = 0
        zinfo.compress_size = compress_size = 0
        # Compressed size can be larger than uncompressed size
        zip64 = self._allowZip64 and zinfo.file_size * 1.05 > zipfile.ZIP64_LIMIT
        yield self.fp.write(zinfo.FileHeader(zip64))

        file_size = 0
        if filename:
            async for buf in self.data_generator(filename):
                file_size = file_size + len(buf)
                CRC = zipfile.crc32(buf, CRC) & 0xffffffff
                if cmpr:
                    buf = await self._run_in_executor(cmpr.compress, buf)
                    compress_size = compress_size + len(buf)
                yield self.fp.write(buf)
        else: # we have an iterable
            for buf in iterable:
                file_size = file_size + len(buf)
                CRC = zipfile.crc32(buf, CRC) & 0xffffffff
                if cmpr:
                    buf = await self._run_in_executor(cmpr.compress, buf)
                    compress_size = compress_size + len(buf)
                yield self.fp.write(buf)

        if cmpr:
            buf = cmpr.flush()
            compress_size = compress_size + len(buf)
            yield self.fp.write(buf)
            zinfo.compress_size = compress_size
        else:
            zinfo.compress_size = file_size
        zinfo.CRC = CRC
        zinfo.file_size = file_size
        if not zip64 and self._allowZip64:
            if file_size > zipfile.ZIP64_LIMIT:
                raise RuntimeError('File size has increased during compressing')
            if compress_size > zipfile.ZIP64_LIMIT:
                raise RuntimeError('Compressed size larger than uncompressed size')

        yield self.fp.write(zinfo.DataDescriptor())
        self.filelist.append(zinfo)
        self.NameToInfo[zinfo.filename] = zinfo

    def _close(self):
        """
        Close the file, and for mode "w" write the ending records.
        """

        if self.fp is None:
            return

        try:
            if self.mode in ('w', 'a') and self._didModify:  # write ending records
                count = 0
                pos1 = self.fp.tell()
                for zinfo in self.filelist:         # write central directory
                    count = count + 1
                    dt = zinfo.date_time
                    dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
                    dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)
                    extra = []
                    if zinfo.file_size > zipfile.ZIP64_LIMIT or zinfo.compress_size > zipfile.ZIP64_LIMIT:
                        extra.append(zinfo.file_size)
                        extra.append(zinfo.compress_size)
                        file_size = 0xffffffff
                        compress_size = 0xffffffff
                    else:
                        file_size = zinfo.file_size
                        compress_size = zinfo.compress_size

                    if zinfo.header_offset > zipfile.ZIP64_LIMIT:
                        extra.append(zinfo.header_offset)
                        header_offset = 0xffffffff
                    else:
                        header_offset = zinfo.header_offset

                    extra_data = zinfo.extra
                    min_version = 0
                    if extra:
                        # Append a ZIP64 field to the extra's
                        extra_data = struct.pack(
                                b'<HH' + b'Q'*len(extra),
                                1, 8*len(extra), *extra) + extra_data
                        min_version = zipfile.ZIP64_VERSION

                    if zinfo.compress_type == zipfile.ZIP_BZIP2:
                        min_version = max(zipfile.BZIP2_VERSION, min_version)
                    elif zinfo.compress_type == zipfile.ZIP_LZMA:
                        min_version = max(zipfile.LZMA_VERSION, min_version)

                    extract_version = max(min_version, zinfo.extract_version)
                    create_version = max(min_version, zinfo.create_version)
                    try:
                        filename, flag_bits = zinfo._encodeFilenameFlags()
                        centdir = struct.pack(structCentralDir,
                            stringCentralDir, create_version,
                            zinfo.create_system, extract_version, zinfo.reserved,
                            flag_bits, zinfo.compress_type, dostime, dosdate,
                            zinfo.CRC, compress_size, file_size,
                            len(filename), len(extra_data), len(zinfo.comment),
                            0, zinfo.internal_attr, zinfo.external_attr,
                            header_offset)
                    except DeprecationWarning:
                        print((structCentralDir, stringCentralDir, create_version,
                            zinfo.create_system, extract_version, zinfo.reserved,
                            zinfo.flag_bits, zinfo.compress_type, dostime, dosdate,
                            zinfo.CRC, compress_size, file_size,
                            len(zinfo.filename), len(extra_data), len(zinfo.comment),
                            0, zinfo.internal_attr, zinfo.external_attr,
                            header_offset), file=sys.stderr)
                        raise
                    yield self.fp.write(centdir)
                    yield self.fp.write(filename)
                    yield self.fp.write(extra_data)
                    yield self.fp.write(zinfo.comment)

                pos2 = self.fp.tell()
                # Write end-of-zip-archive record
                centDirCount = count
                centDirSize = pos2 - pos1
                centDirOffset = pos1
                if (centDirCount >= zipfile.ZIP_FILECOUNT_LIMIT or
                    centDirOffset > zipfile.ZIP64_LIMIT or
                    centDirSize > zipfile.ZIP64_LIMIT):
                    # Need to write the ZIP64 end-of-archive records
                    zip64endrec = struct.pack(
                            structEndArchive64, stringEndArchive64,
                            44, 45, 45, 0, 0, centDirCount, centDirCount,
                            centDirSize, centDirOffset)
                    yield self.fp.write(zip64endrec)

                    zip64locrec = struct.pack(
                            structEndArchive64Locator,
                            stringEndArchive64Locator, 0, pos2, 1)
                    yield self.fp.write(zip64locrec)
                    centDirCount = min(centDirCount, 0xFFFF)
                    centDirSize = min(centDirSize, 0xFFFFFFFF)
                    centDirOffset = min(centDirOffset, 0xFFFFFFFF)

                endrec = struct.pack(structEndArchive, stringEndArchive,
                                    0, 0, centDirCount, centDirCount,
                                    centDirSize, centDirOffset, len(self._comment))
                yield self.fp.write(endrec)
                yield self.fp.write(self._comment)
                self.fp.flush()
        finally:
            fp = self.fp
            self.fp = None
            if not self._filePassed:
                fp.close()
