#!/usr/bin/env python3

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

import struct


# Uncompress data in LZC format, .Z file format
# LZC uses the LZW compression algorithm with a variable dictionary size
# For LZW see https://en.wikipedia.org/wiki/Lempel–Ziv–Welch
# Performance: about 1 MByte/sec, 15-50 times slower than C implementation
def uncompress_LZC(data):
    LZC_NUM_BITS_MIN = 9
    LZC_NUM_BITS_MAX = 16

    in_data = bytearray(data)
    in_len = len(in_data)
    out_data = bytearray()

    if in_len == 0:
        return out_data
    if in_len < 3:
        raise ValueError("invalid length")
    if in_data[0] != 0x1F or in_data[1] != 0x9D:
        raise ValueError("invalid header")

    max_bits = in_data[2] & 0x1F
    if max_bits < LZC_NUM_BITS_MIN or max_bits > LZC_NUM_BITS_MAX:
        raise ValueError("not supported")
    num_items = 1 << max_bits
    blockmode = (in_data[2] & 0x80) != 0

    in_pos = 3
    start_pos = in_pos
    num_bits = LZC_NUM_BITS_MIN
    dict_size = 1 << num_bits
    head = 256
    if blockmode:
        head += 1
    first_sym = True

    # initialize dictionary
    comp_dict = [None] * num_items
    for i in range(0, 256):
        comp_dict[i] = bytes(bytearray([i]))

    buf = buf_bits = 0
    while in_pos < in_len:
        # get next symbol
        try:
            while buf_bits < num_bits:
                buf |= in_data[in_pos] << buf_bits
                buf_bits += 8
                in_pos += 1
            buf, symbol = divmod(buf, dict_size)
            buf_bits -= num_bits
        except IndexError:
            raise ValueError("invalid data")

        # re-initialize dictionary
        if blockmode and symbol == 256:
            # skip to next buffer boundary
            buf = buf_bits = 0
            in_pos += (start_pos - in_pos) % num_bits
            # reset to LZC_NUM_BITS_MIN
            head = 257
            num_bits = LZC_NUM_BITS_MIN
            dict_size = 1 << num_bits
            start_pos = in_pos
            first_sym = True
            continue

        # first symbol
        if first_sym:
            first_sym = False
            if symbol >= 256:
                raise ValueError("invalid data")
            prev = symbol
            out_data.extend(comp_dict[symbol])
            continue

        # dictionary full
        if head >= num_items:
            out_data.extend(comp_dict[symbol])
            continue

        # update compression dictionary
        if symbol < head:
            comp_dict[head] = comp_dict[prev] + comp_dict[symbol][0:1]
        elif symbol == head:
            comp_dict[head] = comp_dict[prev] + comp_dict[prev][0:1]
        else:
            raise ValueError("invalid data")
        prev = symbol

        # output symbol
        out_data.extend(comp_dict[symbol])

        # update head, check for num_bits change
        head += 1
        if head >= dict_size and num_bits < max_bits:
            num_bits += 1
            dict_size = 1 << num_bits
            start_pos = in_pos

    return out_data


# export IOU NVRAM
# NVRAM format: https://github.com/ehlers/IOUtools/blob/master/NVRAM.md
def nvram_export(nvram):
    nvram = bytearray(nvram)

    offset = 0
    # extract startup config
    try:
        (magic, data_format, _, _, _, _, length, _, _, _, _, _) = struct.unpack_from(
            ">HHHHIIIIIHHI", nvram, offset=offset
        )
        offset += 36
        if magic != 0xABCD:
            raise ValueError("no startup config")
        if len(nvram) < offset + length:
            raise ValueError("invalid length")
        startup = nvram[offset : offset + length]
    except struct.error:
        raise ValueError("invalid length")

    # uncompress startup config
    if data_format == 2:
        try:
            startup = uncompress_LZC(startup)
        except ValueError as err:
            raise ValueError("uncompress startup: " + str(err))

    private = None
    try:
        # calculate offset of private header
        length += (4 - length % 4) % 4  # alignment to multiple of 4
        offset += length
        # check for additonal offset of 4
        (magic, data_format) = struct.unpack_from(">HH", nvram, offset=offset + 4)
        if magic == 0xFEDC and data_format == 1:
            offset += 4

        # extract private config
        (magic, data_format, _, _, length) = struct.unpack_from(">HHIII", nvram, offset=offset)
        offset += 16
        if magic == 0xFEDC and data_format == 1:
            if len(nvram) < offset + length:
                raise ValueError("invalid length")
            private = nvram[offset : offset + length]

    # missing private header is not an error
    except struct.error:
        pass

    return (startup, private)


if __name__ == "__main__":
    # Main program
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="%(prog)s exports startup/private configuration from IOU NVRAM file.")
    parser.add_argument("nvram", metavar="NVRAM", help="NVRAM file")
    parser.add_argument("startup", metavar="startup-config", help="startup configuration")
    parser.add_argument("private", metavar="private-config", nargs="?", help="private configuration")
    args = parser.parse_args()

    try:
        fd = open(args.nvram, "rb")
        nvram = fd.read()
        fd.close()
    except OSError as err:
        sys.stderr.write(f"Error reading file: {err}\n")
        sys.exit(1)

    try:
        startup, private = nvram_export(nvram)
    except ValueError as err:
        sys.stderr.write(f"nvram_export: {err}\n")
        sys.exit(3)

    try:
        fd = open(args.startup, "wb")
        fd.write(startup)
        fd.close()
        if args.private is not None:
            if private is None:
                sys.stderr.write("Warning: No private config\n")
            else:
                fd = open(args.private, "wb")
                fd.write(private)
                fd.close()
    except OSError as err:
        sys.stderr.write(f"Error writing file: {err}\n")
        sys.exit(1)
