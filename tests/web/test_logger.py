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

import logging

from gns3server.web.logger import init_logger


def test_init_logger(caplog):

    logger = init_logger(logging.DEBUG)
    logger.debug("DEBUG1")
    assert "DEBUG1" in caplog.text()
    logger.info("INFO1")
    assert "INFO1" in caplog.text()
    logger.warn("WARN1")
    assert "WARN1" in caplog.text()
    logger.error("ERROR1")
    assert "ERROR1" in caplog.text()
    logger.critical("CRITICAL1")
    assert "CRITICAL1" in caplog.text()


def test_init_logger_quiet(caplog):

    logger = init_logger(logging.DEBUG, quiet=True)
    logger.debug("DEBUG1")
    assert "DEBUG1" not in caplog.text()
    logger.info("INFO1")
    assert "INFO1" not in caplog.text()
    logger.warn("WARN1")
    assert "WARN1" not in caplog.text()
    logger.error("ERROR1")
    assert "ERROR1" not in caplog.text()
    logger.critical("CRITICAL1")
    assert "CRITICAL1" not in caplog.text()
