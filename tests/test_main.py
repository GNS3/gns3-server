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

from gns3server import main
from gns3server.config import Config
from gns3server.version import __version__


def test_locale_check():

    try:
        locale.setlocale(locale.LC_ALL, ("fr_FR"))
    except:  # Locale is not available on the server
        return
    main.locale_check()
    assert locale.getlocale() == ('fr_FR', 'UTF-8')


def test_parse_arguments(capsys, tmpdir):

    Config.reset()
    config = Config.instance(str(tmpdir / "test.cfg"))
    server_config = config.get_section_config("Server")

    with pytest.raises(SystemExit):
        main.parse_arguments(["--fail"], server_config)
    out, err = capsys.readouterr()
    assert "usage" in err
    assert "fail" in err
    assert "unrecognized arguments" in err

    with pytest.raises(SystemExit):
        main.parse_arguments(["-v"], server_config)
    out, err = capsys.readouterr()
    assert __version__ in "{}{}".format(out, err)  # Depending of the Python version the location of the version change

    with pytest.raises(SystemExit):
        main.parse_arguments(["--version"], server_config)
    out, err = capsys.readouterr()
    assert __version__ in "{}{}".format(out, err)  # Depending of the Python version the location of the version change

    with pytest.raises(SystemExit):
        main.parse_arguments(["-h"], server_config)
    out, err = capsys.readouterr()
    assert __version__ in out
    assert "optional arguments" in out

    with pytest.raises(SystemExit):
        main.parse_arguments(["--help"], server_config)
    out, err = capsys.readouterr()
    assert __version__ in out
    assert "optional arguments" in out

    assert main.parse_arguments(["--host", "192.168.1.1"], server_config).host == "192.168.1.1"
    assert main.parse_arguments([], server_config).host == "0.0.0.0"
    server_config["host"] = "192.168.1.2"
    assert main.parse_arguments(["--host", "192.168.1.1"], server_config).host == "192.168.1.1"
    assert main.parse_arguments([], server_config).host == "192.168.1.2"

    assert main.parse_arguments(["--port", "8002"], server_config).port == 8002
    assert main.parse_arguments([], server_config).port == 8000
    server_config["port"] = "8003"
    assert main.parse_arguments([], server_config).port == 8003

    assert main.parse_arguments(["--ssl"], server_config).ssl
    assert main.parse_arguments([], server_config).ssl is False
    server_config["ssl"] = "True"
    assert main.parse_arguments([], server_config).ssl

    assert main.parse_arguments(["--certfile", "bla"], server_config).certfile == "bla"
    assert main.parse_arguments([], server_config).certfile == ""

    assert main.parse_arguments(["--certkey", "blu"], server_config).certkey == "blu"
    assert main.parse_arguments([], server_config).certkey == ""

    assert main.parse_arguments(["-L"], server_config).local
    assert main.parse_arguments(["--local"], server_config).local
    assert main.parse_arguments([], server_config).local is False
    server_config["local"] = "True"
    assert main.parse_arguments([], server_config).local

    assert main.parse_arguments(["-A"], server_config).allow
    assert main.parse_arguments(["--allow"], server_config).allow
    assert main.parse_arguments([], server_config).allow is False
    server_config["allow_remote_console"] = "True"
    assert main.parse_arguments([], server_config).allow

    assert main.parse_arguments(["-q"], server_config).quiet
    assert main.parse_arguments(["--quiet"], server_config).quiet
    assert main.parse_arguments([], server_config).quiet is False

    assert main.parse_arguments(["-d"], server_config).debug
    assert main.parse_arguments([], server_config).debug is False
    server_config["debug"] = "True"
    assert main.parse_arguments([], server_config).debug


def test_set_config_with_args():

    config = Config.instance()
    args = main.parse_arguments(["--host",
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
                                 "--debug"],
                                config.get_section_config("Server"))
    main.set_config(args)
    server_config = config.get_section_config("Server")

    assert server_config.getboolean("local")
    assert server_config.getboolean("allow_remote_console")
    assert server_config["host"] == "192.168.1.1"
    assert server_config["port"] == "8001"
    assert server_config.getboolean("ssl")
    assert server_config["certfile"] == "bla"
    assert server_config["certkey"] == "blu"
    assert server_config.getboolean("debug")
