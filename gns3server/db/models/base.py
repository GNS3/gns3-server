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

import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Column, DateTime, func, inspect
from sqlalchemy.types import TypeDecorator, CHAR, VARCHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import as_declarative


@as_declarative()
class Base:
    def asdict(self):

        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}

    def asjson(self):

        return jsonable_encoder(self.asdict())


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class ListException(Exception):
    pass


class ListType(TypeDecorator):
    """
    Save/restore a Python list to/from a database column.
    """

    impl = VARCHAR
    cache_ok = True

    def __init__(self, separator=',', *args, **kwargs):

        self._separator = separator
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if any(self._separator in str(item) for item in value):
                raise ListException(f"List values cannot contain '{self._separator}'"
                                    f"Please use a different separator.")
            return self._separator.join(map(str, value))

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        else:
            return list(map(str, value.split(self._separator)))


class BaseTable(Base):

    __abstract__ = True

    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __mapper_args__ = {"eager_defaults": True}


def generate_uuid():
    return str(uuid.uuid4())
