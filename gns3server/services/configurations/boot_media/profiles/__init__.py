"""The known boot media profiles and the catalog clients see. A new device is one module here and one line below."""

from gns3server.schemas.configurations import normalize_device_type
from gns3server.services.configurations.shared.errors import ConfigurationError

from ..media_profile import BootMediaProfile
from . import (
    cisco_c8000v_autonomous,
    cisco_c8000v_controller,
    cisco_cat9kv,
    cisco_iosv,
    cisco_iosxrv9k,
)

PROFILES: dict[str, BootMediaProfile] = {
    profile.id: profile
    for profile in (
        cisco_cat9kv.PROFILE,
        cisco_c8000v_autonomous.PROFILE,
        cisco_c8000v_controller.PROFILE,
        cisco_iosv.PROFILE,
        cisco_iosxrv9k.PROFILE,
    )
}


def get_profile(profile_id) -> BootMediaProfile:
    try:
        return PROFILES[profile_id]
    except (KeyError, TypeError):
        raise ConfigurationError("startup_media_profile_unknown") from None


def profile_fits_device(profile_id, netmiko_device_type):
    """False when the node's Netmiko device type belongs to another appliance than the profile's.

    A node without a device type fits any profile; an unknown profile is not judged here.
    """
    profile = PROFILES.get(profile_id)
    declared = normalize_device_type(netmiko_device_type)
    return profile is None or not declared or declared in profile.device_types


def list_profiles():
    """Catalog entries for clients: id, title, device_type and description."""
    return [
        {
            "id": profile.id,
            "title": profile.title,
            "device_type": profile.device_types[0],
            "description": profile.description,
        }
        for profile in PROFILES.values()
    ]
