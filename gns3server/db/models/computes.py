#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

from sqlalchemy import Column, String, Integer

from .base import BaseTable, GUID


class Compute(BaseTable):

    __tablename__ = "computes"

    compute_id = Column(GUID, primary_key=True)
    name = Column(String, index=True)
    protocol = Column(String)
    host = Column(String)
    port = Column(Integer)
    user = Column(String)
    password = Column(String)
