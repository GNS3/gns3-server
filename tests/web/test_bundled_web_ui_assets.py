#!/usr/bin/env python
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
The bundled web UI must contain every file its consoles load. Anything built
from a git checkout (GitHub archives, Docker images) ships only what is in git,
and the server answers a missing asset with the web UI page, so a file left out
of git breaks the console at runtime (a JavaScript module served as text/html).
"""

import os
import re

WEB_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "gns3server", "static", "web-ui")

# relative ES module imports and re-exports: import x from "./a.js", export * from "../b.js"
MODULE_IMPORT = re.compile(r"""^\s*(?:import|export)\s+(?:[^'";]*?\s+from\s+)?["'](\.{1,2}/[^"']+)["']""", re.MULTILINE)
SCRIPT_SRC = re.compile(r"""<script[^>]*\ssrc=["']([^"']+)["']""", re.IGNORECASE)


def missing_module_imports(entry: str) -> list[str]:
    """
    Walks the relative imports from an ES module and returns the imported files that do not exist.
    """

    missing, seen, pending = [], set(), [os.path.normpath(entry)]
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        if not os.path.isfile(path):
            missing.append(os.path.relpath(path, WEB_UI_DIR))
            continue
        with open(path, encoding="utf-8") as fd:
            source = fd.read()
        for target in MODULE_IMPORT.findall(source):
            pending.append(os.path.normpath(os.path.join(os.path.dirname(path), target)))
    return sorted(missing)


def test_vnc_console_modules_are_bundled() -> None:

    entry = os.path.join(WEB_UI_DIR, "assets", "vnc-console", "vnc-controller.js")
    assert os.path.isfile(entry)
    assert missing_module_imports(entry) == []


def test_xpra_console_scripts_are_bundled() -> None:

    xpra_dir = os.path.join(WEB_UI_DIR, "assets", "xpra-html5")
    pages = [name for name in os.listdir(xpra_dir) if name.endswith(".html")]
    assert pages
    missing = []
    for page in pages:
        with open(os.path.join(xpra_dir, page), encoding="utf-8") as fd:
            html = fd.read()
        for src in SCRIPT_SRC.findall(html):
            if re.match(r"^(?:[a-z]+:)?//", src):
                continue
            if not os.path.isfile(os.path.join(xpra_dir, src.split("?")[0])):
                missing.append(f"{page}: {src}")
    assert missing == []
