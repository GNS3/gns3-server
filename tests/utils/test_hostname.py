# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 GNS3 Technologies Inc.
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

from gns3server.utils import hostname


def test_ios_hostname_valid_with_valid_hostnames():
    assert hostname.is_ios_hostname_valid("router1")
    assert hostname.is_ios_hostname_valid("switch-2")
    assert hostname.is_ios_hostname_valid("a1-b2-c3")


def test_ios_hostname_valid_with_invalid_hostnames():
    assert not hostname.is_ios_hostname_valid("-router")
    assert not hostname.is_ios_hostname_valid("router-")
    assert not hostname.is_ios_hostname_valid("123router")
    assert not hostname.is_ios_hostname_valid("router@123")
    assert not hostname.is_ios_hostname_valid("router.router")


def test_ios_hostname_valid_with_long_hostnames():
    assert hostname.is_ios_hostname_valid("a" * 63)
    assert not hostname.is_ios_hostname_valid("a" * 64)


def test_ios_hostname_conversion_with_valid_characters():
    assert hostname.to_ios_hostname("validHostname123") == "validHostname123"


def test_ios_hostname_conversion_starts_with_digit():
    assert hostname.to_ios_hostname("1InvalidStart") == "a1InvalidStart"


def test_ios_hostname_conversion_starts_with_special_character():
    assert hostname.to_ios_hostname("@InvalidStart") == "a-InvalidStart"


def test_ios_hostname_conversion_ends_with_special_character():
    assert hostname.to_ios_hostname("InvalidEnd-") == "InvalidEnd0"


def test_ios_hostname_conversion_contains_special_characters():
    assert hostname.to_ios_hostname("Invalid@Hostname!") == "Invalid-Hostname0"


def test_ios_hostname_conversion_exceeds_max_length():
    long_name = "a" * 64
    assert hostname.to_ios_hostname(long_name) == "a" * 63


def test_ios_hostname_conversion_just_right_length():
    exact_length_name = "a" * 63
    assert hostname.to_ios_hostname(exact_length_name) == "a" * 63


def test_rfc1123_hostname_validity_with_valid_hostnames():
    assert hostname.is_rfc1123_hostname_valid("example.com")
    assert hostname.is_rfc1123_hostname_valid("subdomain.example.com")
    assert hostname.is_rfc1123_hostname_valid("example-hyphen.com")
    assert hostname.is_rfc1123_hostname_valid("example.com.")
    assert hostname.is_rfc1123_hostname_valid("123.com")


def test_rfc1123_hostname_validity_with_invalid_hostnames():
    assert not hostname.is_rfc1123_hostname_valid("-example.com")
    assert not hostname.is_rfc1123_hostname_valid("example-.com")
    assert not hostname.is_rfc1123_hostname_valid("example..com")
    assert not hostname.is_rfc1123_hostname_valid("example_com")
    assert not hostname.is_rfc1123_hostname_valid("example.123")


def test_rfc1123_hostname_validity_with_long_hostnames():
    long_hostname = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 61  # 253 characters
    too_long_hostname = long_hostname + "e"
    assert hostname.is_rfc1123_hostname_valid(long_hostname)
    assert not hostname.is_rfc1123_hostname_valid(too_long_hostname)


def test_rfc1123_conversion_hostname_with_valid_characters():
    assert hostname.to_rfc1123_hostname("valid-hostname.example.com") == "valid-hostname.example.com"


def test_rfc1123_conversion_hostname_with_invalid_characters_replaced():
    assert hostname.to_rfc1123_hostname("invalid_hostname!@#$.example") == "invalid-hostname.example"


def test_rfc1123_conversion_hostname_with_trailing_dot_removed():
    assert hostname.to_rfc1123_hostname("hostname.example.com.") == "hostname.example.com"


def test_rfc1123_conversion_hostname_with_labels_exceeding_63_characters():
    long_label = "a" * 64 + ".example.com"
    expected_label = "a" * 63 + ".example.com"
    assert hostname.to_rfc1123_hostname(long_label) == expected_label


def test_rfc1123_conversion_hostname_with_total_length_exceeding_253_characters():
    long_hostname = "a" * 50 + "." + "b" * 50 + "." + "c" * 50 + "." + "d" * 50 + "." + "e" * 50
    assert len(hostname.to_rfc1123_hostname(long_hostname)) <= 253


def test_rfc1123_conversion_hostname_with_all_numeric_tld_replaced():
    assert hostname.to_rfc1123_hostname("hostname.123") == "hostname.invalid"


def rfc1123_hostname_with_multiple_consecutive_invalid_characters():
    assert hostname.to_rfc1123_hostname("hostname!!!.example..com") == "hostname---.example.com"
