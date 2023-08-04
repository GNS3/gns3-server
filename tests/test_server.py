#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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


import pytest
import locale
import tempfile

from gns3server.server import Server
from gns3server.config import Config


def test_locale_check():

    try:
        locale.setlocale(locale.LC_ALL, ("fr_FR", "UTF-8"))
    except:  # Locale is not available on the server
        return
    Server._locale_check()
    assert locale.getlocale() == ('fr_FR', 'UTF-8')


def test_parse_arguments(capsys, config, tmpdir):

    server = Server()
    server_config = config.settings.Server
    with pytest.raises(SystemExit):
        server._parse_arguments(["--fail"])
    out, err = capsys.readouterr()
    assert "usage" in err
    assert "fail" in err
    assert "unrecognized arguments" in err

    # with pytest.raises(SystemExit):
    #     run.parse_arguments(["-v"])
    # out, _ = capsys.readouterr()
    # assert __version__ in out
    # with pytest.raises(SystemExit):
    #     run.parse_arguments(["--version"])
    # out, _ = capsys.readouterr()
    # assert __version__ in out
    #
    # with pytest.raises(SystemExit):
    #     run.parse_arguments(["-h"])
    # out, _ = capsys.readouterr()
    # assert __version__ in out
    # assert "optional arguments" in out
    #
    # with pytest.raises(SystemExit):
    #     run.parse_arguments(["--help"])
    # out, _ = capsys.readouterr()
    # assert __version__ in out
    # assert "optional arguments" in out

    assert server._parse_arguments(["--host", "192.168.1.1"]).host == "192.168.1.1"
    assert server._parse_arguments([]).host == "0.0.0.0"
    server_config.host = "192.168.1.2"
    assert server._parse_arguments(["--host", "192.168.1.1"]).host == "192.168.1.1"
    assert server._parse_arguments([]).host == "192.168.1.2"

    assert server._parse_arguments(["--port", "8002"]).port == 8002
    assert server._parse_arguments([]).port == 3080
    server_config.port = 8003
    assert server._parse_arguments([]).port == 8003

    assert server._parse_arguments(["--ssl"]).ssl
    assert server._parse_arguments([]).ssl is False
    with tempfile.NamedTemporaryFile(dir=str(tmpdir)) as f:
        server_config.certfile = f.name
        server_config.certkey = f.name
        server_config.enable_ssl = True
        assert server._parse_arguments([]).ssl

    assert server._parse_arguments(["--certfile", "bla"]).certfile == "bla"
    assert server._parse_arguments(["--certkey", "blu"]).certkey == "blu"

    assert server._parse_arguments(["-L"]).local
    assert server._parse_arguments(["--local"]).local
    server_config.local = False
    assert server._parse_arguments([]).local is False
    server_config.local = True
    assert server._parse_arguments([]).local

    assert server._parse_arguments(["-A"]).allow
    assert server._parse_arguments(["--allow"]).allow
    assert server._parse_arguments([]).allow is False
    server_config.allow_remote_console = True
    assert server._parse_arguments([]).allow

    assert server._parse_arguments(["-q"]).quiet
    assert server._parse_arguments(["--quiet"]).quiet
    assert server._parse_arguments([]).quiet is False

    assert server._parse_arguments(["-d"]).debug
    assert server._parse_arguments(["--debug"]).debug
    assert server._parse_arguments([]).debug is False


def test_set_config_with_args(tmpdir):

    server = Server()
    config = Config.instance()
    with tempfile.NamedTemporaryFile(dir=str(tmpdir)) as f:
        certfile = f.name
        certkey = f.name
        args = server._parse_arguments(["--host",
                                        "192.168.1.1",
                                        "--local",
                                        "--allow",
                                        "--port",
                                        "8001",
                                        "--ssl",
                                        "--certfile",
                                        certfile,
                                        "--certkey",
                                        certkey,
                                        "--debug"])
        server._set_config_defaults_from_command_line(args)

    server_config = config.settings.Server
    assert server_config.local
    assert server_config.allow_remote_console
    assert server_config.host
    assert server_config.port
    assert server_config.enable_ssl
    assert server_config.certfile
    assert server_config.certkey
