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

import pytest
from pydantic import ValidationError

from gns3server.schemas.controller.templates.docker_templates import DockerTemplate
from gns3server.schemas.controller.templates.qemu_templates import QemuTemplate


class TestDockerTemplateNameValidation:
    """Test RFC 1123 hostname validation for Docker templates"""

    def test_valid_docker_template_names(self):
        """Test that valid Docker template names are accepted"""

        valid_names = [
            "cisco-xrd",
            "cisco-xrd-1",
            "docker-container",
            "my-container-123",
            "alpine",
            "ubuntu-latest",
        ]

        for name in valid_names:
            template = DockerTemplate(name=name, image="alpine")
            assert template.name == name

    def test_valid_docker_template_names_with_dots(self):
        """Test that names with dots are valid according to RFC 1123"""

        valid_names = [
            "container.test",  # dots separate labels
            "my.container.name",  # multiple labels
        ]

        for name in valid_names:
            template = DockerTemplate(name=name, image="alpine")
            assert template.name == name

    def test_invalid_docker_template_names(self):
        """Test that invalid Docker template names are rejected"""

        invalid_names = [
            "cisco_xrd",  # underscore not allowed
            "cisco_xrd-1",  # underscore not allowed
            "my_container",  # underscore not allowed
            "-container",  # cannot start with hyphen
            "container-",  # cannot end with hyphen
            "my container",  # space not allowed
        ]

        for name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                DockerTemplate(name=name, image="alpine")
            assert "invalid name" in str(exc_info.value).lower()


class TestQemuTemplateNameValidation:
    """Test RFC 1123 hostname validation for Qemu templates"""

    def test_valid_qemu_template_names(self):
        """Test that valid Qemu template names are accepted"""

        valid_names = [
            "my-vm",
            "my-vm-1",
            "qemu-guest",
            "alpine-vm",
            "ubuntu-test",
        ]

        for name in valid_names:
            template = QemuTemplate(name=name)
            assert template.name == name

    def test_invalid_qemu_template_names(self):
        """Test that invalid Qemu template names are rejected"""

        invalid_names = [
            "my_vm",  # underscore not allowed
            "my_vm-1",  # underscore not allowed
            "test_vm",  # underscore not allowed
            "-vm",  # cannot start with hyphen
            "vm-",  # cannot end with hyphen
            "my vm",  # space not allowed
        ]

        for name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                QemuTemplate(name=name)
            assert "invalid name" in str(exc_info.value).lower()
