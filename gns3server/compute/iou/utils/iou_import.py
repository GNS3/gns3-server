#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# To use python v2.7 change the first line to:
#!/usr/bin/env python

# Copyright (C) 2015 Bernhard Ehlers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
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
iou_import imports startup/private configuration into IOU NVRAM file.

usage: iou_import [-h] [-c size] NVRAM startup-config [private-config]

positional arguments:
  NVRAM                 NVRAM file
  startup-config        startup configuration
  private-config        private configuration

optional arguments:
  -h, --help            show this help message and exit
  -c size, --create size
                        create NVRAM file, size in kByte
"""

import argparse
import sys


# extract 16 bit unsigned int from data
def get_uint16(data, off):
    return data[off] << 8 | data[off + 1]


# extract 32 bit unsigned int from data
def get_uint32(data, off):
    return data[off] << 24 | data[off + 1] << 16 | data[off + 2] << 8 | data[off + 3]


# insert 16 bit unsigned int into data
def put_uint16(data, off, value):
    data[off] = (value >> 8) & 0xff
    data[off + 1] = value & 0xff


# insert 32 bit unsigned int into data
def put_uint32(data, off, value):
    data[off] = (value >> 24) & 0xff
    data[off + 1] = (value >> 16) & 0xff
    data[off + 2] = (value >> 8) & 0xff
    data[off + 3] = value & 0xff


# calculate padding
def padding(off, ios, nvram_len):
    pad = (4 - off % 4) % 4             # padding to alignment of 4
    # add 4 if IOS <= 15.0 or NVRAM area >= 64KB
    if (ios <= 0x0F00 or nvram_len >= 64 * 1024) and pad != 0:
        pad += 4
    return pad


# update checksum
def checksum(data, start, end):
    put_uint16(data, start + 4, 0)      # set checksum to 0

    chk = 0
    idx = start
    while idx < end - 1:
        chk += get_uint16(data, idx)
        idx += 2
    if idx < end:
        chk += data[idx] << 8

    while chk >> 16:
        chk = (chk & 0xffff) + (chk >> 16)

    chk = chk ^ 0xffff
    put_uint16(data, start + 4, chk)    # set checksum


# import IOU NVRAM
def nvram_import(nvram, startup, private, size):
    BASE_ADDRESS = 0x10000000
    DEFAULT_IOS = 0x0F04               # IOS 15.4

    # check size parameter
    if size is not None and (size < 8 or size > 1024):
        raise ValueError('invalid size')

    # create new nvram if nvram is empty or has wrong size
    if nvram is None or (size is not None and len(nvram) != size * 1024):
        nvram = bytearray([0] * (size * 1024))
    else:
        nvram = bytearray(nvram)

    # check nvram size
    nvram_len = len(nvram)
    if nvram_len < 8 * 1024 or nvram_len > 1024 * 1024 or nvram_len % 1024 != 0:
        raise ValueError('invalid NVRAM length')
    nvram_len = nvram_len // 2

    # get size of current config
    config_len = 0
    ios = None
    try:
        if get_uint16(nvram, 0) == 0xABCD:
            ios = get_uint16(nvram, 6)
            config_len = 36 + get_uint32(nvram, 16)
            config_len += padding(config_len, ios, nvram_len)
            if get_uint16(nvram, config_len) == 0xFEDC:
                config_len += 16 + get_uint32(nvram, config_len + 12)
    except IndexError:
        raise ValueError('unknown nvram format')
    if config_len > nvram_len:
        raise ValueError('unknown nvram format')

    # calculate max. config size
    max_config = nvram_len - 2 * 1024             # reserve 2k for files
    idx = max_config
    empty_sector = bytearray([0] * 1024)
    while True:
        idx -= 1024
        if idx < config_len:
            break
        # if valid file header:
        if get_uint16(nvram, idx + 0) == 0xDCBA and \
           get_uint16(nvram, idx + 4) < 8 and \
           get_uint16(nvram, idx + 6) <= 992:
            max_config = idx
        elif nvram[idx:idx + 1024] != empty_sector:
            break

    # import startup config
    startup = bytearray(startup)
    if ios is None:
        # Target IOS version is unknown. As some IOU don't work nicely with
        # the padding of a different version, the startup config is padded
        # with '\n' to the alignment of 4.
        ios = DEFAULT_IOS
        startup.extend([ord('\n')] * ((4 - len(startup) % 4) % 4))
    new_nvram = bytearray([0] * 36)                             # startup hdr
    put_uint16(new_nvram, 0, 0xABCD)                           # magic
    put_uint16(new_nvram, 2, 1)                                # raw data
    put_uint16(new_nvram, 6, ios)                              # IOS version
    put_uint32(new_nvram, 8, BASE_ADDRESS + 36)                  # start address
    put_uint32(new_nvram, 12, BASE_ADDRESS + 36 + len(startup))   # end address
    put_uint32(new_nvram, 16, len(startup))                     # length
    new_nvram.extend(startup)
    new_nvram.extend([0] * padding(len(new_nvram), ios, nvram_len))

    # import private config
    if private is None:
        private = bytearray()
    else:
        private = bytearray(private)
    offset = len(new_nvram)
    new_nvram.extend([0] * 16)                                  # private hdr
    put_uint16(new_nvram, 0 + offset, 0xFEDC)                  # magic
    put_uint16(new_nvram, 2 + offset, 1)                       # raw data
    put_uint32(new_nvram, 4 + offset,
               BASE_ADDRESS + offset + 16)                      # start address
    put_uint32(new_nvram, 8 + offset,
               BASE_ADDRESS + offset + 16 + len(private))       # end address
    put_uint32(new_nvram, 12 + offset, len(private))            # length
    new_nvram.extend(private)

    # add rest
    if len(new_nvram) > max_config:
        raise ValueError('NVRAM size too small')
    new_nvram.extend([0] * (max_config - len(new_nvram)))
    new_nvram.extend(nvram[max_config:])

    checksum(new_nvram, 0, nvram_len)

    return new_nvram


if __name__ == '__main__':
    # Main program

    def check_size(string):
        try:
            value = int(string)
        except ValueError:
            raise argparse.ArgumentTypeError('invalid int value: ' + string)
        if value < 8 or value > 1024:
            raise argparse.ArgumentTypeError('size must be 8..1024')
        return value

    parser = argparse.ArgumentParser(description='%(prog)s imports startup/private configuration into IOU NVRAM file.')
    parser.add_argument('-c', '--create', metavar='size', type=check_size,
                        help='create NVRAM file, size in kByte')
    parser.add_argument('nvram', metavar='NVRAM',
                        help='NVRAM file')
    parser.add_argument('startup', metavar='startup-config',
                        help='startup configuration')
    parser.add_argument('private', metavar='private-config', nargs='?',
                        help='private configuration')
    args = parser.parse_args()

    try:
        if args.create is None:
            fd = open(args.nvram, 'rb')
            nvram = fd.read()
            fd.close()
        else:
            nvram = None
        fd = open(args.startup, 'rb')
        startup = fd.read()
        fd.close()
        if args.private is None:
            private = None
        else:
            fd = open(args.private, 'rb')
            private = fd.read()
            fd.close()
    except (IOError, OSError) as err:
        sys.stderr.write("Error reading file: {}\n".format(err))
        sys.exit(1)

    try:
        nvram = nvram_import(nvram, startup, private, args.create)
    except ValueError as err:
        sys.stderr.write("nvram_import: {}\n".format(err))
        sys.exit(3)

    try:
        fd = open(args.nvram, 'wb')
        fd.write(nvram)
        fd.close()
    except (IOError, OSError) as err:
        sys.stderr.write("Error writing file: {}\n".format(err))
        sys.exit(1)
