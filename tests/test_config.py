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


import configparser
import time
import os

from gns3server.config import Config


def load_config(tmpdir, settings):
    """
    Create a configuration file for
    the test.

    :params tmpdir: Temporary directory
    :params settings: Configuration settings
    :returns: Configuration instance
    """

    path = write_config(tmpdir, settings)
    return Config(files=[path])


def write_config(tmpdir, settings):
    """
    Write a configuration file for the test.

    :params tmpdir: Temporary directory
    :params settings: Configuration settings
    :returns: File path
    """

    path = str(tmpdir / "server.conf")

    config = configparser.ConfigParser()
    config.read_dict(settings)
    with open(path, "w+") as f:
        config.write(f)
    return path


def test_get_section_config(tmpdir):

    config = load_config(tmpdir, {
        "Server": {
            "host": "127.0.0.1"
        }
    })
    assert dict(config.get_section_config("Server")) == {"host": "127.0.0.1"}


def test_set_section_config(tmpdir):

    config = load_config(tmpdir, {
        "Server": {
            "host": "127.0.0.1",
            "local": "false"
        }
    })
    assert dict(config.get_section_config("Server")) == {"host": "127.0.0.1", "local": "false"}
    config.set_section_config("Server", {"host": "192.168.1.1", "local": True})
    assert dict(config.get_section_config("Server")) == {"host": "192.168.1.1", "local": "true"}


def test_set(tmpdir):

    config = load_config(tmpdir, {
        "Server": {
            "host": "127.0.0.1"
        }
    })
    assert dict(config.get_section_config("Server")) == {"host": "127.0.0.1"}
    config.set("Server", "host", "192.168.1.1")
    assert dict(config.get_section_config("Server")) == {"host": "192.168.1.1"}


def test_reload(tmpdir):

    config = load_config(tmpdir, {
        "Server": {
            "host": "127.0.0.1"
        }
    })
    assert dict(config.get_section_config("Server")) == {"host": "127.0.0.1"}

    config.set_section_config("Server", {"host": "192.168.1.1"})
    assert dict(config.get_section_config("Server")) == {"host": "192.168.1.1"}

    path = write_config(tmpdir, {
        "Server": {
            "host": "192.168.1.2"
        }
    })

    config.reload()
    assert dict(config.get_section_config("Server")) == {"host": "192.168.1.1"}
