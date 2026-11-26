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
from gns3server.services.configurations.boot_media.profiles import cisco_viptela
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.password_hash import sha512_crypt

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
ADMIN_HASH = "$6$salt1234$Zm9vYmFyYmF6UXV4.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ab"
WITH_ADMIN = f"system\n host-name x\n aaa\n  user admin\n   password {ADMIN_HASH}\n  !\n  user ops\n   password $6$o$h\n  !\n !\n!\n"
NO_ADMIN = "system\n host-name x\n aaa\n  user ops\n   password $6$o$h\n   group netadmin\n  !\n !\n!\n"


def test_registry_lists_the_supported_profiles():
    assert set(PROFILES) == {
        "cisco-cat9kv",
        "cisco-c8000v-autonomous",
        "cisco-c8000v-controller",
        "cisco-iosv",
        "cisco-iosxrv9k",
        "cisco-nxosv9k",
        "cisco-viptela",
    }
    assert all(profile.id == key for key, profile in PROFILES.items())
    assert {entry["id"]: entry["device_type"] for entry in list_profiles()} == {
        "cisco-cat9kv": "cisco_ios_telnet",
        "cisco-c8000v-autonomous": "cisco_ios_telnet",
        "cisco-c8000v-controller": "cisco_ios_telnet",
        "cisco-iosv": "cisco_ios_telnet",
        "cisco-iosxrv9k": "cisco_xr",
        "cisco-nxosv9k": "cisco_nxos",
        "cisco-viptela": "cisco_viptela",
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


def nxos_text(content, password=None):
    context = MediaContext(node_id=NODE, admin_password=password)
    return get_profile("cisco-nxosv9k").files(content, context)["nxos_config.txt"].decode()


def test_nxosv9k_stores_the_text_as_nxos_config_with_lf_line_endings():
    profile = get_profile("cisco-nxosv9k")
    assert profile.files("hostname N9K\r\ninterface mgmt0\r\n", CONTEXT) == {
        "nxos_config.txt": b"hostname N9K\ninterface mgmt0\n"
    }
    assert profile.device_types == ("cisco_nxos",) and profile.volume_label == "CONFIG"


def test_nxosv9k_keeps_the_admin_account_of_a_captured_listing():
    text = "hostname N9K\nusername admin password 5 $5$abc$def  role network-admin\n"
    assert nxos_text(text, "Lab#Pass1") == text


def test_nxosv9k_uses_the_saved_password_when_the_text_has_no_usable_admin():
    expected = "no password strength-check\nusername admin password cisco123 role network-admin\nhostname N9K\n"
    assert nxos_text("hostname N9K\n", "cisco123") == expected
    # A factory account (empty ``!`` hash) or a masked secret cannot be loaded back: it is replaced.
    assert nxos_text("hostname N9K\nusername admin password 5 !  role network-admin\n", "cisco123") == expected
    assert nxos_text("hostname N9K\nusername admin password ***** role network-admin\n", "cisco123") == expected


def test_nxosv9k_without_a_usable_password_leaves_the_text_alone():
    assert nxos_text("hostname N9K\n") == "hostname N9K\n"
    assert nxos_text("hostname N9K\n", "with space") == "hostname N9K\n"


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


def test_viptela_media_is_a_nocloud_seed_with_a_loader():
    profile = get_profile("cisco-viptela")
    config = "system\n host-name vsmart1\n site-id 100\n!\n"
    files = profile.files(config, CONTEXT)
    assert profile.volume_label == "cidata" and set(files) == {"user-data", "meta-data"}
    assert files["meta-data"] == f"instance-id: gns3-{NODE}\n".encode()
    assert files["user-data"].startswith(b"#cloud-config\n")
    document = yaml.safe_load(files["user-data"])
    written = {entry["path"]: entry for entry in document["write_files"]}
    startup = written[f"{cisco_viptela.ROOT}/startup.cfg"]
    assert startup["encoding"] == "b64" and base64.b64decode(startup["content"]).decode() == config
    assert base64.b64decode(written[f"{cisco_viptela.ROOT}/load.sh"]["content"]).decode() == cisco_viptela.LOADER
    assert json.dumps(document["runcmd"]).count("load.sh") == 1
    assert "confd_load -l -m -F c" in cisco_viptela.LOADER
    # No vpn sections in the text: the factory vpns are left alone.
    assert f"{cisco_viptela.ROOT}/replace-vpn" not in written


def test_a_text_that_defines_vpns_replaces_the_factory_ones_in_one_transaction():
    text = "system\n host-name x\n!\nvpn 0\n interface eth1\n  no shutdown\n !\n!\nvpn 512\n!\n"
    files = get_profile("cisco-viptela").files(text, CONTEXT)
    paths = {entry["path"] for entry in yaml.safe_load(files["user-data"])["write_files"]}
    assert f"{cisco_viptela.ROOT}/replace-vpn" in paths
    assert 'scope="-p /vpn"' in cisco_viptela.LOADER
    # Indented "vpn" words inside other sections are not vpn sections.
    assert not cisco_viptela.defines_vpns("snmp\n trap target vpn 512 10.0.0.1 162\n!\n")
    assert cisco_viptela.defines_vpns(text)


def test_the_loader_retries_early_boot_errors_and_reports_failures_on_the_console():
    loader = cisco_viptela.LOADER
    # Transient ConfD helper errors (the real symptom was a usmentry write error) are retried...
    assert "usmentry" in loader and "sleep 10" in loader and "-lt 40" in loader
    # ...anything else is final, and both outcomes are printed unmistakably.
    assert "console 'GNS3: startup configuration applied.'" in loader
    assert 'console "GNS3: startup configuration FAILED:' in loader
    assert "<hash>" in loader  # encrypted values never reach the console


def test_viptela_account_password_hashes_are_delivered_byte_for_byte():
    # The config's own `aaa user` hashes become the login; they must not be altered.
    text = "system\n aaa\n  user admin\n   password $6$abcdefgh$Zm9v/YmFy.KQ0\n  !\n !\n!\n"
    files = get_profile("cisco-viptela").files(text, CONTEXT)
    startup = next(e for e in yaml.safe_load(files["user-data"])["write_files"] if e["path"].endswith("startup.cfg"))
    assert base64.b64decode(startup["content"]).decode() == text


def initial_admin_cfg(text, password=None):
    from gns3server.services.configurations.boot_media import MediaContext as Context

    files = get_profile("cisco-viptela").files(text, Context(node_id=NODE, admin_password=password))
    written = {e["path"]: e for e in yaml.safe_load(files["user-data"])["write_files"]}
    entry = written.get(f"{cisco_viptela.ROOT}/initial-admin.cfg")
    return base64.b64decode(entry["content"]).decode() if entry else None, files


def test_the_texts_own_admin_hash_is_loaded_first_and_wins_over_the_node_password():
    config, files = initial_admin_cfg(WITH_ADMIN, "NodePassword1")
    assert config == f"system\n aaa\n  user admin\n   password {ADMIN_HASH}\n  !\n !\n!\n"
    assert "NodePassword1" not in files["user-data"].decode()


def test_the_node_password_is_hashed_here_when_the_text_has_no_admin():
    config, files = initial_admin_cfg(NO_ADMIN, "NodePassword1")
    value = config.split("password ")[1].split("\n")[0]
    assert value.startswith("$6$") and len(value.split("$")[2]) == 16
    assert value == sha512_crypt("NodePassword1", value.split("$")[2])
    # Only a hash ever reaches the media; other aaa users are not part of the account step.
    assert "NodePassword1" not in files["user-data"].decode() and "ops" not in config
    # Deterministic for a node: same node, same password, same media.
    assert initial_admin_cfg(NO_ADMIN, "NodePassword1")[1] == files


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


@pytest.mark.parametrize("profile", [controller.PROFILE, cisco_viptela.PROFILE], ids=lambda profile: profile.id)
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


def test_a_plaintext_admin_password_is_kept_out_of_the_merged_configuration():
    text = "system\n host-name a\n aaa\n  user admin\n   password plaintext\n  !\n !\n!\n"
    for password in (None, "Saved-Pass-1"):
        files = cisco_viptela.PROFILE.files(text, MediaContext(node_id=NODE, admin_password=password))
        document = json.loads(files["user-data"].split(b"\n", 1)[1])
        by_name = {
            entry["path"].rsplit("/", 1)[1]: base64.b64decode(entry["content"]) for entry in document["write_files"]
        }
        assert b"plaintext" not in by_name["startup.cfg"] and b"host-name a" in by_name["startup.cfg"]
        assert ("initial-admin.cfg" in by_name) is bool(password)


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
