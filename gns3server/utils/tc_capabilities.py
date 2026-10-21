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
uBridge ``tc capabilities`` vocabulary: the reply parser and the server-side
policy built on top of it. Shared by the compute side (the per-node probe in
DockerVM and the standalone /capabilities probe) and the controller side
(filter availability), so both gate on the same rules.

Reply shape (additive by contract — unknown keys pass through untouched):
``netem=<kw,...>;ebpf=0|1;cbpf=0|1[;ebpf_modes=<mode,...>]``
"""

# eBPF classifier modes that shipped before the ``ebpf_modes`` field existed
# (uBridge feature/tc-precision): the field was added together with the
# window-mode correction, so an ebpf=1 build that does not emit it has
# exactly these. window is the only mode whose semantics changed after
# release — it is never offered unless the build declares the token.
LEGACY_EBPF_MODES = ("nth", "quota", "flow")

# GNS3 filter type -> eBPF classifier mode token
FILTER_EBPF_MODES = {
    "frequency_drop": "nth",
    "quota": "quota",
    "window_drop": "window",
}

# GNS3 filter type -> netem keyword (netem= token in the capabilities reply)
FILTER_NETEM_KEYWORDS = {
    "rate": "rate",
    "reorder": "reorder",
    "gemodel": "gemodel",
    "duplicate": "dup",
    "seed": "seed",
    "limit": "limit",
}


def parse_tc_capabilities(reply):
    """
    Parse the payload of a ``tc capabilities`` reply into a dict.

    :param reply: reply payload (first reply line, no status code)
    :returns: dict of keys to values, both strings
    """

    caps = {}
    for entry in (reply or "").split(";"):
        key, _, value = entry.partition("=")
        if key:
            caps[key.strip()] = value.strip()
    return caps


def usable_ebpf_modes(caps):
    """
    The eBPF classifier modes this uBridge build can actually run: a mode is
    usable iff ``ebpf=1`` and its token is listed in ``ebpf_modes``. Builds
    that do not emit the field predate it and keep the modes that shipped
    with it (LEGACY_EBPF_MODES) — gating on ``ebpf=1`` alone would silently
    accept window_drop on the pre-correction build, which drops it into
    back-to-back windows.

    :param caps: parsed ``tc capabilities`` dict
    :returns: tuple of usable mode tokens, in reply order
    """

    if caps.get("ebpf") != "1":
        return ()
    if "ebpf_modes" not in caps:
        return LEGACY_EBPF_MODES
    return tuple(mode for mode in caps["ebpf_modes"].split(",") if mode)
