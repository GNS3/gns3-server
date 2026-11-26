"""The files each profile puts on its media, and the registry that exposes them."""

import pytest

from gns3server.services.configurations.boot_media import (
    PROFILES,
    BootMediaProfile,
    MediaContext,
    get_profile,
    list_profiles,
)
from gns3server.services.configurations.shared.errors import ConfigurationError

NODE = "7b4e1f5a-0c3e-4d58-9d2b-1f6f2f1f0a11"
CONTEXT = MediaContext(node_id=NODE)


def test_registry_lists_the_supported_profiles():
    assert set(PROFILES) == {
        "cisco-c8000v-autonomous",
    }
    assert all(profile.id == key for key, profile in PROFILES.items())
    assert {entry["id"]: entry["device_type"] for entry in list_profiles()} == {
        "cisco-c8000v-autonomous": "cisco_ios_telnet",
    }
    assert all(
        set(entry) == {"id", "title", "device_type", "description"} and entry["title"] for entry in list_profiles()
    )


@pytest.mark.parametrize("unknown", ["nope", "", None, 7])
def test_an_unknown_profile_has_a_registered_error_code(unknown):
    with pytest.raises(ConfigurationError, match="startup_media_profile_unknown"):
        get_profile(unknown)


def test_a_profile_rejects_an_unsafe_volume_label():
    with pytest.raises(ValueError, match="volume label"):
        BootMediaProfile("x", "X", "x", ("cisco_ios_telnet",), "bad label; rm", lambda content, context: {})


@pytest.mark.parametrize("profile", PROFILES.values(), ids=lambda profile: profile.id)
@pytest.mark.parametrize("content", ["", "   \n\t", "hostname a\x00b\n", "x" * (2 * 1024 * 1024 + 1)])
def test_every_profile_refuses_unusable_text(profile, content):
    with pytest.raises(ConfigurationError, match="configuration_invalid_content"):
        profile.files(content, CONTEXT)


def test_profile_validation_rejects_unsafe_file_names():
    broken = BootMediaProfile("y", "Y", "y", ("cisco_ios_telnet",), "L", lambda content, context: {"../x": b"1"})
    with pytest.raises(ConfigurationError, match="configuration_invalid_content"):
        broken.files("hostname r1\n", CONTEXT)


@pytest.mark.parametrize(
    "profile_id,text",
    [
        ("cisco-c8000v-autonomous", "hostname R1\r\ninterface Gi1\r\n ip address 10.0.0.1 255.255.255.0\r\nend\r\n"),
    ],
    ids=["c8000v-autonomous"],
)
def test_ios_xe_profiles_store_the_text_unchanged_as_iosxe_config(profile_id, text):
    profile = get_profile(profile_id)
    assert profile.files(text, CONTEXT) == {"iosxe_config.txt": text.encode()}
    assert profile.volume_label == "GNS3_BOOT"
    assert profile.media == "cdrom"
    assert profile.device_types == ("cisco_ios_telnet",)


def test_the_context_never_shows_the_password():
    assert "secret" not in repr(MediaContext(node_id=NODE, admin_password="secret"))


def test_a_disk_profile_needs_a_label_that_fits_a_fat_volume():
    BootMediaProfile("short", "T", "d", ("x",), "ABCDEFGHIJK", lambda text, context: {"f": b"x"}, media="disk")
    with pytest.raises(ValueError, match="too long"):
        BootMediaProfile("long", "T", "d", ("x",), "ABCDEFGHIJKL", lambda text, context: {"f": b"x"}, media="disk")
    # A CD-ROM label may be longer.
    BootMediaProfile("long", "T", "d", ("x",), "ABCDEFGHIJKL", lambda text, context: {"f": b"x"})
    with pytest.raises(ValueError, match="media kind"):
        BootMediaProfile("odd", "T", "d", ("x",), "LABEL", lambda text, context: {"f": b"x"}, media="tape")


@pytest.mark.parametrize(
    "password,usable", [("cisco123", True), ("p@ss!word", True), ("with space", False), ("", False), (None, False)]
)
def test_the_saved_password_is_used_only_when_it_is_one_printable_token(password, usable):
    from gns3server.services.configurations.boot_media.media_profile import plain_password

    assert plain_password(MediaContext(node_id=NODE, admin_password=password)) == (password if usable else None)


def test_media_paths_may_be_nested_and_directories_are_empty():
    from gns3server.services.configurations.boot_media.media_profile import valid_entry

    assert valid_entry("config/bootstrap.xml", b"x") and valid_entry("license/", b"")
    assert not valid_entry("license/", b"x") and not valid_entry("config/x", b"")
    for bad in ("../x", "/abs", "a//b", "a/../b", ".hidden", "a/b/c/d/e/f", ""):
        assert not valid_entry(bad, b"x")
