#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import os
import asyncio
import struct


class Qcow2Error(Exception):
    pass


class Qcow2:
    """
    Allows to parse a Qcow2 file
    """

    def __init__(self, path):

        self._path = path
        self._reload()

    def _reload(self):
        # Each QCOW2 file begins with a header, in big endian format, as follows:
        #
        # typedef struct QCowHeader {
        #     uint32_t magic;
        #     uint32_t version;
        #
        #     uint64_t backing_file_offset;
        #     uint32_t backing_file_size;
        #
        #     uint32_t cluster_bits;
        #     uint64_t size; /* in bytes */
        #     uint32_t crypt_method;
        #
        #     uint32_t l1_size;
        #     uint64_t l1_table_offset;
        #
        #     uint64_t refcount_table_offset;
        #     uint32_t refcount_table_clusters;
        #
        #     uint32_t nb_snapshots;
        #     uint64_t snapshots_offset;
        # } QCowHeader;

        struct_format = ">IIQi"
        with open(self._path, 'rb') as f:
            content = f.read(struct.calcsize(struct_format))
            try:
                self.magic, self.version, self.backing_file_offset, self.backing_file_size = struct.unpack_from(struct_format, content)

            except struct.error:
                raise Qcow2Error("Invalid file header for {}".format(self._path))

        if self.magic != 1363560955:  # The first 4 bytes contain the characters 'Q', 'F', 'I' followed by 0xfb.
            raise Qcow2Error("Invalid magic for {}".format(self._path))

    @property
    def backing_file(self):
        """
        When using linked clone this will return the path to the base image

        :returns: None if it's not a linked clone, the path otherwise
        """

        with open(self._path, 'rb') as f:
            f.seek(self.backing_file_offset)
            content = f.read(self.backing_file_size)

        path = content.decode()
        if len(path) == 0:
            return None
        return path

    @asyncio.coroutine
    def rebase(self, qemu_img, base_image):
        """
        Rebase a linked clone in order to use the correct disk

        :param qemu_img: Path to the qemu-img binary
        :param base_image: Path to the base image
        """

        if not os.path.exists(base_image):
            raise FileNotFoundError(base_image)
        command = [qemu_img, "rebase", "-u", "-b", base_image, self._path]
        process = yield from asyncio.create_subprocess_exec(*command)
        retcode = yield from process.wait()
        if retcode != 0:
            raise Qcow2Error("Could not rebase the image")
        self._reload()
