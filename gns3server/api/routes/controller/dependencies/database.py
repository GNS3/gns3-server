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

from typing import Callable, Type
from fastapi import Depends
from starlette.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.db.repositories.base import BaseRepository


async def get_db_session(request: HTTPConnection) -> AsyncSession:

    async with AsyncSession(request.app.state._db_engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.close()


def get_repository(repo: Type[BaseRepository]) -> Callable:
    def get_repo(db_session: AsyncSession = Depends(get_db_session)) -> Type[BaseRepository]:
        return repo(db_session)

    return get_repo
