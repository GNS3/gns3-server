#
# Software Name : GNS3 server
# Version: 3
# SPDX-FileCopyrightText: Copyright (c) 2023 Orange Business Services
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This software is distributed under the GPL-3.0 or any later version,
# the text of which is available at https://www.gnu.org/licenses/gpl-3.0.txt
# or see the "LICENSE" file for more details.
#
# Author: Sylvain MATHIEU
#

"""
API route for privileges
"""

from typing import List
from gns3server.db.repositories.rbac import RbacRepository
from .dependencies.database import get_repository
from fastapi import APIRouter, Depends
import logging

from gns3server import schemas

log = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.Privilege],
)
async def get_privileges(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Privilege]:
    """
    Get all privileges.

    Required privilege: None
    """

    return await rbac_repo.get_privileges()
