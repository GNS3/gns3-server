"""The files each profile puts on its media, and the registry that exposes them."""

import base64
import email
import hashlib
import json
from email import policy

import pytest
import yaml

from gns3server.services.configurations.boot_media import (
    PROFILES,
    BootMediaProfile,
    MediaContext,
    get_profile,
    list_profiles,
)
from gns3server.services.configurations.boot_media.profiles import cisco_c8000v_controller as controller
from gns3server.services.configurations.shared.errors import ConfigurationError

NODE = "7b4e1f5a-0c3e-4d58-9d2b-1f6f2f1f0a11"
CONTEXT = MediaContext(node_id=NODE)
SDWAN = (
    "hostname edge1\n"
    "username admin privilege 15 secret 9 $9$abc\n"
    "system\n"
    " host-name             edge1\n"
    ' organization-name     "Lab Org"\n'
    " vbond 10.9.9.9\n"
    "!\n"
    "sdwan\n"
    " interface GigabitEthernet1\n"
    "  tunnel-interface\n"
    " exit\n"
)
BOOTSTRAP = (
    'Content-Type: multipart/mixed; boundary="==BOUNDARY=="\nMIME-Version: 1.0\n\n'
    "--==BOUNDARY==\nContent-Type: text/cloud-config\n\n#cloud-config\nvinitparam:\n - uuid : abc\n--==BOUNDARY==--\n"
)
XR_ADMIN = "username admin\n group root-lr\n group cisco-support\n secret 0 cisco123\n!\n"
XR_LISTING = (
    "!! IOS XR Configuration 26.1.1\nhostname XR1\n"
    "username lab\n group root-lr\n group cisco-support\n secret 10 $6$abc$def\n!\nend\n"
)


def test_registry_lists_the_supported_profiles():
    assert set(PROFILES) == {
        "cisco-cat9kv",
        "cisco-c8000v-autonomous",
        "cisco-c8000v-controller",
        "cisco-iosv",
        "cisco-iosxrv9k",
    }
    assert all(profile.id == key for key, profile in PROFILES.items())
    assert {entry["id"]: entry["device_type"] for entry in list_profiles()} == {
        "cisco-cat9kv": "cisco_ios_telnet",
        "cisco-c8000v-autonomous": "cisco_ios_telnet",
        "cisco-c8000v-controller": "cisco_ios_telnet",
        "cisco-iosv": "cisco_ios_telnet",
        "cisco-iosxrv9k": "cisco_xr",
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
        ("cisco-cat9kv", "hostname SW1\r\nusername admin privilege 15 secret 9 $9$abc\r\nend\r\n"),
    ],
    ids=["c8000v-autonomous", "cat9kv"],
)
def test_ios_xe_profiles_store_the_text_unchanged_as_iosxe_config(profile_id, text):
    profile = get_profile(profile_id)
    assert profile.files(text, CONTEXT) == {"iosxe_config.txt": text.encode()}
    assert profile.volume_label == "GNS3_BOOT"
    assert profile.media == "cdrom"
    assert profile.device_types == ("cisco_ios_telnet",)


def xr_text(content, password=None):
    context = MediaContext(node_id=NODE, admin_password=password)
    return get_profile("cisco-iosxrv9k").files(content, context)["iosxr_config.txt"].decode()


def test_iosxrv9k_stores_the_text_as_iosxr_config_with_lf_line_endings():
    profile = get_profile("cisco-iosxrv9k")
    assert profile.files("hostname XR1\r\nend\r\n", CONTEXT) == {"iosxr_config.txt": b"hostname XR1\nend\n"}
    assert profile.device_types == ("cisco_xr",) and profile.volume_label == "config-1"


def test_iosxrv9k_keeps_the_user_of_a_captured_listing():
    assert xr_text(XR_LISTING, "Lab#Pass1") == XR_LISTING


def test_iosxrv9k_uses_the_saved_password_when_the_text_has_no_usable_user():
    assert xr_text("hostname XR1\nend\n", "cisco123") == XR_ADMIN + "hostname XR1\nend\n"
    # A user without a loadable secret (masked, or no secret at all) is replaced by the admin user.
    masked = "hostname XR1\nusername lab\n group root-lr\n secret 10 *****\n!\nend\n"
    assert xr_text(masked, "cisco123") == XR_ADMIN + "hostname XR1\nend\n"


def test_iosxrv9k_counts_the_older_password_line_as_a_usable_secret():
    listing = "hostname XR1\nusername lab\n group root-lr\n password 7 0822455D0A16\n!\nend\n"
    assert xr_text(listing, "cisco123") == listing


def test_iosxrv9k_without_a_usable_password_leaves_the_text_alone():
    assert xr_text("hostname XR1\nend\n") == "hostname XR1\nend\n"
    assert xr_text("hostname XR1\nend\n", "with space") == "hostname XR1\nend\n"


def iosv_files(content):
    return get_profile("cisco-iosv").files(content, CONTEXT)


def test_iosv_puts_the_text_and_its_md5_on_a_disk_with_lf_line_endings():
    profile = get_profile("cisco-iosv")
    files = iosv_files("hostname R1\r\nend")
    assert files["ios_config.txt"] == b"hostname R1\nend\n"
    # The checksum file is the MD5 of the configuration file, as on the vendor's own startup disk.
    expected = hashlib.md5(b"hostname R1\nend\n", usedforsecurity=False).hexdigest()
    assert files["ios_config_checksum"] == expected.encode() + b"\n"
    assert profile.media == "disk" and profile.device_types == ("cisco_ios_telnet",)


def test_iosv_rewrites_the_caret_c_banner_delimiter_of_a_captured_listing():
    listing = "hostname R1\nbanner exec ^C\nline one\nline two\n^C\nbanner motd ^Chello lab^C\nend\n"
    text = iosv_files(listing)["ios_config.txt"].decode()
    assert text == "hostname R1\nbanner exec %\nline one\nline two\n%\nbanner motd %hello lab%\nend\n"


def test_iosv_picks_a_delimiter_that_is_not_in_the_banner_text():
    text = iosv_files("banner motd ^C100% sure~|^C\nend\n")["ios_config.txt"].decode()
    assert text == "banner motd @100% sure~|@\nend\n"


@pytest.mark.parametrize("banner", ["banner motd ^Cnever closed\nend\n", "banner motd ^C%~|@^C\nend\n"])
def test_iosv_refuses_a_banner_it_cannot_write_safely(banner):
    with pytest.raises(ConfigurationError, match="configuration_invalid_content"):
        iosv_files(banner)


def test_iosv_drops_the_header_lines_of_a_pasted_listing():
    listing = "Building configuration...\n\nCurrent configuration : 1234 bytes\n!\nhostname R1\nend\n"
    assert iosv_files(listing)["ios_config.txt"].decode() == "\n!\nhostname R1\nend\n"
    more = "Using 1234 out of 262144 bytes\n!\nhostname R1\nend\n"
    assert iosv_files(more)["ios_config.txt"].decode() == "!\nhostname R1\nend\n"


def test_iosv_does_not_use_the_saved_password():
    context = MediaContext(node_id=NODE, admin_password="cisco123")
    profile = get_profile("cisco-iosv")
    assert profile.files("hostname R1\n", context) == profile.files("hostname R1\n", CONTEXT)


def test_a_mime_bootstrap_is_used_as_is():
    files = get_profile("cisco-c8000v-controller").files(BOOTSTRAP, CONTEXT)
    assert files == {"ciscosdwan_cloud_init.cfg": BOOTSTRAP.encode()}


def test_plain_sdwan_text_is_wrapped_in_a_multipart_bootstrap():
    files = get_profile("cisco-c8000v-controller").files(SDWAN, CONTEXT)
    assert list(files) == ["ciscosdwan_cloud_init.cfg"]
    message = email.message_from_bytes(files["ciscosdwan_cloud_init.cfg"], policy=policy.default)
    assert message.get_content_type() == "multipart/mixed" and not message.defects
    cloud, boothook = message.iter_parts()
    assert cloud.get_content_type() == "text/cloud-config" and boothook.get_content_type() == "text/cloud-boothook"
    parameters = yaml.safe_load(cloud.get_content())["vinitparam"]
    assert parameters == [
        {"uuid": f"C8K-{NODE}"},
        {"otp": "0" * 32},
        {"vbond": "10.9.9.9"},
        {"org": "Lab Org"},
        {"rcc": True},
    ]
    # The CLI text rides unchanged, indentation included, behind the boothook marker.
    assert boothook.get_content() == "#cloud-boothook\n" + SDWAN


@pytest.mark.parametrize("password", [None, "admin", "saved-password"])
def test_sdwan_text_without_a_user_is_refused_even_with_a_saved_password(password):
    context = MediaContext(node_id=NODE, admin_password=password)
    with pytest.raises(ConfigurationError, match="configuration_login_required"):
        get_profile("cisco-c8000v-controller").files("hostname edge1\n sdwan\n", context)


def test_missing_system_values_get_lab_placeholders():
    cloud = email.message_from_bytes(
        get_profile("cisco-c8000v-controller").files("hostname edge1\nusername admin secret x\n", CONTEXT)[
            "ciscosdwan_cloud_init.cfg"
        ],
        policy=policy.default,
    )
    parameters = yaml.safe_load(next(cloud.iter_parts()).get_content())["vinitparam"]
    assert {"vbond": controller.DEFAULT_VBOND} in parameters and {"org": controller.DEFAULT_ORG} in parameters


def test_the_context_never_shows_the_password():
    assert "secret" not in repr(MediaContext(node_id=NODE, admin_password="secret"))


@pytest.mark.parametrize(
    "line,vbond,org",
    [
        (' organization-name "Lab Org"\n vbond 10.0.0.1 port 12346\n', "10.0.0.1", "Lab Org"),
        # Device quoting is not JSON: a backslash or trailing words must not crash the wrapper.
        (' organization-name "a\\q" extra\n vbond 10.0.0.2\n', "10.0.0.2", "a\\q"),
        (' organization-name "unterminated\n', controller.DEFAULT_VBOND, "unterminated"),
    ],
)
def test_system_values_are_read_like_the_cli_prints_them(line, vbond, org):
    text = "username lab secret x\nsystem\n system-ip 1.1.1.1\n" + line + "!\n"
    assert controller.system_value(text, "vbond") in (vbond, None)
    payload = controller.PROFILE.files(text, CONTEXT)[controller.TARGET].decode()
    assert f" - vbond : {json.dumps(vbond)}\n" in payload
    if org != "unterminated":
        assert f" - org : {json.dumps(org)}\n" in payload


@pytest.mark.parametrize("profile", [controller.PROFILE], ids=lambda profile: profile.id)
def test_parsed_crlf_text_is_delivered_with_lf_line_endings(profile):
    files = profile.files(
        "username lab secret x\r\nsystem\r\n host-name r1\r\n vbond 10.0.0.1\r\n!\r\nvpn 0\r\n!\r\n", CONTEXT
    )
    for data in files.values():
        data = (
            base64.b64decode(json.loads(data.split(b"\n", 1)[1])["write_files"][0]["content"])
            if data.startswith(b"#cloud-config")
            else data
        )
        assert b"\r" not in data


def test_controller_text_keeps_its_own_users_and_a_manager_bootstrap_is_never_modified():
    from gns3server.services.configurations.boot_media.profiles.cisco_c8000v_controller import render

    def render_body(text):
        return render(text, MediaContext(node_id="n1"))["ciscosdwan_cloud_init.cfg"]

    body = render_body("hostname c1\nusername lab privilege 15 password Lab1\n").decode()
    assert body.count("username ") == 1
    bootstrap = "Content-Type: multipart/mixed; boundary=x\nMIME-Version: 1.0\n\n--x--\n"
    assert render_body(bootstrap) == bootstrap.encode()


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
