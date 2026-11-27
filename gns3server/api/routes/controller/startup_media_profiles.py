"""Read-only catalog of native boot media profiles (see services/configurations/boot_media)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from gns3server.services.configurations.boot_media import list_profiles

from .dependencies.authentication import get_current_active_user

router = APIRouter(dependencies=[Depends(get_current_active_user)])


class StartupMediaProfileInfo(BaseModel):
    id: str
    title: str
    device_type: str
    description: str


@router.get("", response_model=list[StartupMediaProfileInfo])
async def get_startup_media_profiles():
    """Profiles a QEMU node can select in ``startup_media_profile``."""
    return list_profiles()
