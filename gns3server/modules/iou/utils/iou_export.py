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

# This utility is a stripped down version of dynamips' nvram_export,
# ported from C to Python, see https://github.com/GNS3/dynamips
# nvram_export is (c) 2013 Flávio J. Saraiva

"""
iou_export exports startup/private configuration from IOU NVRAM file.

usage: iou_export [-h] NVRAM startup-config [private-config]

positional arguments:
  NVRAM           NVRAM file
  startup-config  startup configuration
  private-config  private configuration

optional arguments:
  -h, --help      show this help message and exit
"""

import argparse
import sys


# Uncompress data in .Z file format.
# Ported from dynamips' fs_nvram.c to python
# Adapted from 7zip's ZDecoder.cpp, which is licensed under LGPL 2.1.
def uncompress_LZC(data):
    LZC_NUM_BITS_MIN = 9
    LZC_NUM_BITS_MAX = 16

    in_data = bytearray(data)
    in_len = len(in_data)
    out_data = bytearray()

    if in_len == 0:
        return out_data
    if in_len < 3:
        raise ValueError('invalid length')
    if in_data[0] != 0x1F or in_data[1] != 0x9D:
        raise ValueError('invalid header')

    maxbits = in_data[2] & 0x1F
    numItems = 1 << maxbits
    blockMode = (in_data[2] & 0x80) != 0
    if maxbits < LZC_NUM_BITS_MIN or maxbits > LZC_NUM_BITS_MAX:
        raise ValueError('not supported')

    parents = [0] * numItems
    suffixes = [0] * numItems

    in_pos = 3
    numBits = LZC_NUM_BITS_MIN
    head = 256
    if blockMode:
        head += 1

    needPrev = 0
    bitPos = 0
    numBufBits = 0

    parents[256] = 0
    suffixes[256] = 0

    buf_extend = bytearray([0] * 3)

    while True:
        # fill buffer, when empty
        if numBufBits == bitPos:
            buf_len = min(in_len - in_pos, numBits)
            buf = in_data[in_pos:in_pos + buf_len] + buf_extend
            numBufBits = buf_len << 3
            bitPos = 0
            in_pos += buf_len

        # extract next symbol
        bytePos = bitPos >> 3
        symbol = buf[bytePos] | buf[bytePos + 1] << 8 | buf[bytePos + 2] << 16
        symbol >>= bitPos & 7
        symbol &= (1 << numBits) - 1
        bitPos += numBits

        # check for special conditions: end, bad data, re-initialize dictionary
        if bitPos > numBufBits:
            break
        if symbol >= head:
            raise ValueError('invalid data')
        if blockMode and symbol == 256:
            numBufBits = bitPos = 0
            numBits = LZC_NUM_BITS_MIN
            head = 257
            needPrev = 0
            continue

        # convert symbol to string
        stack = []
        cur = symbol
        while cur >= 256:
            stack.append(suffixes[cur])
            cur = parents[cur]
        stack.append(cur)
        if needPrev:
            suffixes[head - 1] = cur
            if symbol == head - 1:
                stack[0] = cur
        stack.reverse()
        out_data.extend(stack)

        # update parents, check for numBits change
        if head < numItems:
            needPrev = 1
            parents[head] = symbol
            head += 1
            if head > (1 << numBits):
                if numBits < maxbits:
                    numBufBits = bitPos = 0
                    numBits += 1
        else:
            needPrev = 0

    return out_data


# extract 16 bit unsigned int from data
def get_uint16(data, off):
    return data[off] << 8 | data[off + 1]


# extract 32 bit unsigned int from data
def get_uint32(data, off):
    return data[off] << 24 | data[off + 1] << 16 | data[off + 2] << 8 | data[off + 3]


# export IOU NVRAM
def nvram_export(nvram):
    nvram = bytearray(nvram)

    # extract startup config
    offset = 0
    if len(nvram) < offset + 36:
        raise ValueError('invalid length')
    if get_uint16(nvram, offset + 0) != 0xABCD:
        raise ValueError('no startup config')
    format = get_uint16(nvram, offset + 2)
    length = get_uint32(nvram, offset + 16)
    offset += 36
    if len(nvram) < offset + length:
        raise ValueError('invalid length')
    startup = nvram[offset:offset + length]

    # compressed startup config
    if format == 2:
        try:
            startup = uncompress_LZC(startup)
        except ValueError as err:
            raise ValueError('uncompress startup: ' + str(err))

    offset += length
    # alignment to multiple of 4
    offset = (offset + 3) & ~3
    # check for additonal offset of 4
    if len(nvram) >= offset + 8 and \
       get_uint16(nvram, offset + 4) == 0xFEDC and \
       get_uint16(nvram, offset + 6) == 1:
        offset += 4

    # extract private config
    private = None
    if len(nvram) >= offset + 16 and get_uint16(nvram, offset + 0) == 0xFEDC:
        length = get_uint32(nvram, offset + 12)
        offset += 16
        if len(nvram) >= offset + length:
            private = nvram[offset:offset + length]

    return (startup, private)


if __name__ == '__main__':
    # Main program

    parser = argparse.ArgumentParser(description='%(prog)s exports startup/private configuration from IOU NVRAM file.')
    parser.add_argument('nvram', metavar='NVRAM',
                        help='NVRAM file')
    parser.add_argument('startup', metavar='startup-config',
                        help='startup configuration')
    parser.add_argument('private', metavar='private-config', nargs='?',
                        help='private configuration')
    args = parser.parse_args()

    try:
        fd = open(args.nvram, 'rb')
        nvram = fd.read()
        fd.close()
    except (IOError, OSError) as err:
        sys.stderr.write("Error reading file: {}\n".format(err))
        sys.exit(1)

    try:
        startup, private = nvram_export(nvram)
    except ValueError as err:
        sys.stderr.write("nvram_export: {}\n".format(err))
        sys.exit(3)

    try:
        fd = open(args.startup, 'wb')
        fd.write(startup)
        fd.close()
        if args.private is not None:
            if private is None:
                sys.stderr.write("Warning: No private config\n")
            else:
                fd = open(args.private, 'wb')
                fd.write(private)
                fd.close()
    except (IOError, OSError) as err:
        sys.stderr.write("Error writing file: {}\n".format(err))
        sys.exit(1)
