#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
The `tc capabilities` reply parser and the eBPF mode policy shared by the
compute probe and the controller filter availability.
"""

from gns3server.utils.tc_capabilities import (
    LEGACY_EBPF_MODES,
    parse_tc_capabilities,
    usable_ebpf_modes,
)


def test_parse_full_reply():

    caps = parse_tc_capabilities("netem=delay,jitter,loss;ebpf=1;cbpf=0;ebpf_modes=nth,quota,window,flow")
    assert caps == {
        "netem": "delay,jitter,loss",
        "ebpf": "1",
        "cbpf": "0",
        "ebpf_modes": "nth,quota,window,flow",
    }


def test_parse_legacy_reply_without_modes():
    """A build predating the field (and unknown future keys) passes through."""

    caps = parse_tc_capabilities("netem=delay;ebpf=1;cbpf=1")
    assert caps == {"netem": "delay", "ebpf": "1", "cbpf": "1"}


def test_parse_empty_reply():

    assert parse_tc_capabilities("") == {}
    assert parse_tc_capabilities(None) == {}


def test_usable_modes_require_ebpf():
    """The mode list is a build fact; ebpf is the runtime gate for all of them."""

    assert usable_ebpf_modes({"ebpf": "0", "ebpf_modes": "nth,quota,window,flow"}) == ()
    assert usable_ebpf_modes({}) == ()


def test_usable_modes_from_token_list():

    caps = {"ebpf": "1", "ebpf_modes": "nth,quota,window,flow"}
    assert usable_ebpf_modes(caps) == ("nth", "quota", "window", "flow")


def test_usable_modes_legacy_build_keeps_shipped_modes():
    """No field: the modes that shipped before it — everything but window."""

    assert usable_ebpf_modes({"ebpf": "1"}) == LEGACY_EBPF_MODES
    assert "window" not in LEGACY_EBPF_MODES


def test_window_never_usable_without_token():
    """The pre-correction build reported ebpf=1 with broken window semantics."""

    assert "window" not in usable_ebpf_modes({"ebpf": "1"})
    assert "window" not in usable_ebpf_modes({"ebpf": "1", "ebpf_modes": "nth,quota"})
