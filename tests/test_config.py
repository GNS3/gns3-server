# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
import pytest

from gns3server.config import Config
from gns3server.config import ServerConfig
from pydantic import ValidationError


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


@pytest.mark.parametrize(
    "setting, value, result",
    (
            ("allowed_interfaces", "", []),
            ("allowed_interfaces", "eth0", ["eth0"]),
            ("allowed_interfaces", "eth1,eth2", ["eth1", "eth2"]),
            ("additional_images_paths", "", []),
            ("additional_images_paths", "/path/to/dir1", ["/path/to/dir1"]),
            ("additional_images_paths", "/path/to/dir1;/path/to/dir2", ["/path/to/dir1", "/path/to/dir2"])
    )
)
def test_server_settings_to_list(tmpdir, setting: str, value: str, result: str):

    config = load_config(tmpdir, {
        "Server": {
            setting: value
        }
    })

    assert config.settings.model_dump(exclude_unset=True)["Server"][setting] == result


def test_reload(tmpdir):

    config = load_config(tmpdir, {
        "Server": {
            "host": "127.0.0.1"
        }
    })

    assert config.settings.Server.host == "127.0.0.1"

    write_config(tmpdir, {
        "Server": {
            "host": "192.168.1.2"
        }
    })

    config.reload()
    assert config.settings.Server.host == "192.168.1.2"


def test_server_password_hidden():

    server_settings = {"Server": {"compute_password": "password123"}}
    config = ServerConfig(**server_settings)
    assert str(config.Server.compute_password) == "**********"
    assert config.Server.compute_password.get_secret_value() == "password123"


@pytest.mark.parametrize(
    "settings, exception_expected",
    (
            ({"protocol": "https1"}, True),
            ({"console_start_port_range": 15000, "console_end_port_range": 20000}, False),
            ({"console_start_port_range": 0}, True),
            ({"console_start_port_range": 68000}, True),
            ({"console_end_port_range": 15000}, False),
            ({"console_end_port_range": 0}, True),
            ({"console_end_port_range": 68000}, True),
            ({"console_start_port_range": 10000, "console_end_port_range": 5000}, True),
            ({"vnc_console_start_port_range": 6000}, False),
            ({"vnc_console_start_port_range": 1000}, True),
            ({"vnc_console_end_port_range": 6000}, False),
            ({"vnc_console_end_port_range": 1000}, True),
            ({"vnc_console_start_port_range": 7000, "vnc_console_end_port_range": 6000}, True),
            ({"enable_ssl": True, "certfile": "/path/to/certfile", "certkey": "/path/to/certkey"}, True),
            ({"enable_ssl": True}, True),
            ({"enable_ssl": True, "certfile": "/path/to/certfile"}, True),
            ({"enable_ssl": True, "certkey": "/path/to/certkey"}, True)
    )
)
def test_server_settings(settings: dict, exception_expected: bool):

    server_settings = {"Server": settings}

    if exception_expected:
        with pytest.raises(ValidationError):
            ServerConfig(**server_settings)
    else:
        ServerConfig(**server_settings)


@pytest.mark.parametrize(
    "settings, exception_expected",
    (
            ({"vmnet_start_range": 0}, True),
            ({"vmnet_start_range": 256}, True),
            ({"vmnet_end_range": 0}, True),
            ({"vmnet_end_range": 256}, True),
            ({"vmnet_start_range": 2, "vmnet_end_range": 10}, False),
            ({"vmnet_start_range": 5, "vmnet_end_range": 3}, True)
    )
)
def test_vmware_settings(settings: dict, exception_expected: bool):

    vmware_settings = {"VMware": settings}

    if exception_expected:
        with pytest.raises(ValidationError):
            ServerConfig(**vmware_settings)
    else:
        ServerConfig(**vmware_settings)
