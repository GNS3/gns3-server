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

from gns3server import run
from gns3server.config import Config
from gns3server.version import __version__


def test_locale_check():

    try:
        locale.setlocale(locale.LC_ALL, ("fr_FR", "UTF-8"))
    except:  # Locale is not available on the server
        return
    run.locale_check()
    assert locale.getlocale() == ('fr_FR', 'UTF-8')


def test_parse_arguments(capsys, tmpdir):

    Config.reset()
    config = Config.instance([str(tmpdir / "test.cfg")])
    server_config = config.get_section_config("Server")

    with pytest.raises(SystemExit):
        run.parse_arguments(["--fail"])
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

    assert run.parse_arguments(["--host", "192.168.1.1"]).host == "192.168.1.1"
    assert run.parse_arguments([]).host == "0.0.0.0"
    server_config["host"] = "192.168.1.2"
    assert run.parse_arguments(["--host", "192.168.1.1"]).host == "192.168.1.1"
    assert run.parse_arguments([]).host == "192.168.1.2"

    assert run.parse_arguments(["--port", "8002"]).port == 8002
    assert run.parse_arguments([]).port == 3080
    server_config["port"] = "8003"
    assert run.parse_arguments([]).port == 8003

    assert run.parse_arguments(["--ssl"]).ssl
    assert run.parse_arguments([]).ssl is False
    server_config["ssl"] = "True"
    assert run.parse_arguments([]).ssl

    assert run.parse_arguments(["--certfile", "bla"]).certfile == "bla"
    assert run.parse_arguments([]).certfile == ""

    assert run.parse_arguments(["--certkey", "blu"]).certkey == "blu"
    assert run.parse_arguments([]).certkey == ""

    assert run.parse_arguments(["-L"]).local
    assert run.parse_arguments(["--local"]).local
    assert run.parse_arguments([]).local is False
    server_config["local"] = "True"
    assert run.parse_arguments([]).local

    assert run.parse_arguments(["-A"]).allow
    assert run.parse_arguments(["--allow"]).allow
    assert run.parse_arguments([]).allow is False
    server_config["allow_remote_console"] = "True"
    assert run.parse_arguments([]).allow

    assert run.parse_arguments(["-q"]).quiet
    assert run.parse_arguments(["--quiet"]).quiet
    assert run.parse_arguments([]).quiet is False

    assert run.parse_arguments(["-d"]).debug
    assert run.parse_arguments([]).debug is False
    server_config["debug"] = "True"
    assert run.parse_arguments([]).debug


def test_set_config_with_args():

    config = Config.instance()
    args = run.parse_arguments(["--host",
                                "192.168.1.1",
                                "--local",
                                "--allow",
                                "--port",
                                "8001",
                                "--ssl",
                                "--certfile",
                                "bla",
                                "--certkey",
                                "blu",
                                "--debug"])
    run.set_config(args)
    server_config = config.get_section_config("Server")

    assert server_config.getboolean("local")
    assert server_config.getboolean("allow_remote_console")
    assert server_config["host"] == "192.168.1.1"
    assert server_config["port"] == "8001"
    assert server_config.getboolean("ssl")
    assert server_config["certfile"] == "bla"
    assert server_config["certkey"] == "blu"
    assert server_config.getboolean("debug")
