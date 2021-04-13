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

import struct


# calculate padding
def padding(length, start_address):
    pad = -length % 4  # padding to alignment of 4
    # extra padding if pad != 0 and big start_address
    if pad != 0 and (start_address & 0x80000000) != 0:
        pad += 4
    return pad


# update checksum
def checksum(data, start, end):
    chk = 0
    # calculate checksum of first two words
    for word in struct.unpack_from(">2H", data, start):
        chk += word

    # add remaining words, ignoring old checksum at offset 4
    struct_format = f">{(end - start - 6) // 2:d}H"
    for word in struct.unpack_from(struct_format, data, start + 6):
        chk += word

    # handle 16 bit overflow
    while chk >> 16:
        chk = (chk & 0xFFFF) + (chk >> 16)
    chk = chk ^ 0xFFFF

    # save checksum
    struct.pack_into(">H", data, start + 4, chk)


# import IOU NVRAM
# NVRAM format: https://github.com/ehlers/IOUtools/blob/master/NVRAM.md
def nvram_import(nvram, startup, private, size):
    DEFAULT_IOS = 0x0F04  # IOS 15.4
    base_address = 0x10000000

    # check size parameter
    if size is not None and (size < 8 or size > 1024):
        raise ValueError("invalid size")

    # create new nvram if nvram is empty or has wrong size
    if nvram is None or (size is not None and len(nvram) != size * 1024):
        nvram = bytearray([0] * (size * 1024))
    else:
        nvram = bytearray(nvram)

    # check nvram size
    nvram_len = len(nvram)
    if nvram_len < 8 * 1024 or nvram_len > 1024 * 1024 or nvram_len % 1024 != 0:
        raise ValueError("invalid NVRAM length")
    nvram_len = nvram_len // 2

    # get size of current config
    config_len = 0
    try:
        (magic, _, _, ios, start_addr, _, length, _, _, _, _, _) = struct.unpack_from(">HHHHIIIIIHHI", nvram, offset=0)
        if magic == 0xABCD:
            base_address = start_addr - 36
            config_len = 36 + length + padding(length, base_address)
            (magic, _, _, _, length) = struct.unpack_from(">HHIII", nvram, offset=config_len)
            if magic == 0xFEDC:
                config_len += 16 + length
        else:
            ios = None
    except struct.error:
        raise ValueError("unknown nvram format")
    if config_len > nvram_len:
        raise ValueError("unknown nvram format")

    # calculate max. config size
    max_config = nvram_len - 2 * 1024  # reserve 2k for files
    idx = max_config
    empty_sector = bytearray([0] * 1024)
    while True:
        idx -= 1024
        if idx < config_len:
            break
        # if valid file header:
        (magic, _, flags, length, _) = struct.unpack_from(">HHHH24s", nvram, offset=idx)
        if magic == 0xDCBA and flags < 8 and length <= 992:
            max_config = idx
        elif nvram[idx : idx + 1024] != empty_sector:
            break

    # import startup config
    new_nvram = bytearray()
    if ios is None:
        # Target IOS version is unknown. As some IOU don't work nicely with
        # the padding of a different version, the startup config is padded
        # with '\n' to the alignment of 4.
        ios = DEFAULT_IOS
        startup += b"\n" * (-len(startup) % 4)
    new_nvram.extend(
        struct.pack(
            ">HHHHIIIIIHHI",
            0xABCD,  # magic
            1,  # raw data
            0,  # checksum, not yet calculated
            ios,  # IOS version
            base_address + 36,  # start address
            base_address + 36 + len(startup),  # end address
            len(startup),  # length
            0,
            0,
            0,
            0,
            0,
        )
    )
    new_nvram.extend(startup)
    new_nvram.extend([0] * padding(len(new_nvram), base_address))

    # import private config
    if private is None:
        private = b""
    offset = len(new_nvram)
    new_nvram.extend(
        struct.pack(
            ">HHIII",
            0xFEDC,  # magic
            1,  # raw data
            base_address + offset + 16,  # start address
            base_address + offset + 16 + len(private),  # end address
            len(private),
        )
    )  # length
    new_nvram.extend(private)

    # add rest
    if len(new_nvram) > max_config:
        raise ValueError("NVRAM size too small")
    new_nvram.extend([0] * (max_config - len(new_nvram)))
    new_nvram.extend(nvram[max_config:])

    checksum(new_nvram, 0, nvram_len)

    return new_nvram


if __name__ == "__main__":
    # Main program
    import argparse
    import sys

    def check_size(string):
        try:
            value = int(string)
        except ValueError:
            raise argparse.ArgumentTypeError("invalid int value: " + string)
        if value < 8 or value > 1024:
            raise argparse.ArgumentTypeError("size must be 8..1024")
        return value

    parser = argparse.ArgumentParser(description="%(prog)s imports startup/private configuration into IOU NVRAM file.")
    parser.add_argument("-c", "--create", metavar="size", type=check_size, help="create NVRAM file, size in kByte")
    parser.add_argument("nvram", metavar="NVRAM", help="NVRAM file")
    parser.add_argument("startup", metavar="startup-config", help="startup configuration")
    parser.add_argument("private", metavar="private-config", nargs="?", help="private configuration")
    args = parser.parse_args()

    try:
        if args.create is None:
            fd = open(args.nvram, "rb")
            nvram = fd.read()
            fd.close()
        else:
            nvram = None
        fd = open(args.startup, "rb")
        startup = fd.read()
        fd.close()
        if args.private is None:
            private = None
        else:
            fd = open(args.private, "rb")
            private = fd.read()
            fd.close()
    except OSError as err:
        sys.stderr.write(f"Error reading file: {err}\n")
        sys.exit(1)

    try:
        nvram = nvram_import(nvram, startup, private, args.create)
    except ValueError as err:
        sys.stderr.write(f"nvram_import: {err}\n")
        sys.exit(3)

    try:
        fd = open(args.nvram, "wb")
        fd.write(nvram)
        fd.close()
    except OSError as err:
        sys.stderr.write(f"Error writing file: {err}\n")
        sys.exit(1)
