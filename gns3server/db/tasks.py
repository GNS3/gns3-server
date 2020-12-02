#!/usr/bin/env python
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

from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .models import Base

import logging
log = logging.getLogger(__name__)


async def connect_to_db() -> None:

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            log.info("Successfully connected to the database")
    except SQLAlchemyError as e:
        log.error(f"Error while connecting to the database: {e}")
