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

import os

from unittest.mock import patch

from gns3server.version import __version__
from gns3server.controller import Controller
from gns3server.utils.get_resource import get_resource


def get_static(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.abspath(os.path.join(current_dir, '..', '..', 'gns3server', 'static')), filename)


def test_index(http_root):
    response = http_root.get('/')
    assert response.status == 200
    html = response.html
    assert "Website" in html
    assert __version__ in html


def test_controller(http_root, async_run):
    project = async_run(Controller.instance().add_project(name="test"))
    response = http_root.get('/controller')
    assert "test" in response.html
    assert response.status == 200


def test_compute(http_root):
    response = http_root.get('/compute')
    assert response.status == 200


def test_project(http_root, async_run):
    project = async_run(Controller.instance().add_project(name="test"))
    response = http_root.get('/projects/{}'.format(project.id))
    assert response.status == 200


def test_web_ui(http_root, tmpdir):
    with patch('gns3server.utils.get_resource.get_resource') as mock:
        mock.return_value = str(tmpdir)
        os.makedirs(str(tmpdir / 'web-ui'))
        tmpfile = get_static('web-ui/testing.txt')
        with open(tmpfile, 'w+') as f:
            f.write('world')
        response = http_root.get('/static/web-ui/testing.txt')
        assert response.status == 200
    os.remove(get_static('web-ui/testing.txt'))


def test_web_ui_not_found(http_root, tmpdir):
    with patch('gns3server.utils.get_resource.get_resource') as mock:
        mock.return_value = str(tmpdir)

        response = http_root.get('/static/web-ui/not-found.txt')
        # should serve web-ui/index.html
        assert response.status == 200


def test_v1(http_root):
    """
    The old api v1 raise a 429
    """
    response = http_root.get('/v1/version')
    assert response.status == 200
