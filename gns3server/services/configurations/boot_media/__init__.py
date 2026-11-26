"""Native boot media: startup configuration delivered on a CD-ROM or a small FAT disk the guest reads at boot.

Public API: ``get_profile`` / ``list_profiles`` (the registry in ``profiles``),
``BootMediaProfile`` and ``MediaContext`` (``media_profile``). Staging lives in ``staging``,
the QEMU attachment in ``qemu_attachment`` and the ISO and FAT disk builders in ``iso_builder`` and
``disk_builder``; these are imported by path so that importing the profiles never pulls in the compute.
"""

from .media_profile import BootMediaProfile, MediaContext
from .profiles import PROFILES, get_profile, list_profiles

__all__ = ["PROFILES", "BootMediaProfile", "MediaContext", "get_profile", "list_profiles"]
