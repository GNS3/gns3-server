"""Console replay failures report a safe, masked stage/index/command/device-error context."""

import pytest

from gns3server.services.configurations.shared.failure_context import describe_failure, failure_context, mask_text


def test_generic_replay_context_has_index_total_and_masked_command():
    context = failure_context(
        {
            "phase": "replay",
            "command_index": 3,
            "command_total": 9,
            "command": "username bob secret 9 $9$abc",
            "device_error": "% Invalid input " + "x" * 300,
            "config": "PRIVATE",
        }
    )
    assert context["command"] == "username bob secret <masked>"
    assert len(context["device_error"]) <= 120
    assert "config" not in context and context["command_total"] == 9


@pytest.mark.parametrize(
    "text,expected",
    [
        ("snmp community public RO", "snmp community <masked>"),
        ("aaa user admin password abc", "aaa user admin password <masked>"),
        ("crypto pre-shared-key abc", "crypto pre-shared-key <masked>"),
        ("enable secret 5 $1$abc$def", "enable secret <masked>"),
        ("tunnel $6$salt$hash", "tunnel <masked>"),
        ("description 'my thing'", "description <masked>"),
        ('banner login "unterminated text', "banner login <masked>"),
        ("token " + "A" * 60, "token <masked>"),
        ("interface eth0", "interface eth0"),
        ("/user add name=admin password=Hunter2 group=full", "/user add name=admin password=<masked> group=full"),
        ("set wpa2-pre-shared-key=Hunter2", "set wpa2-pre-shared-key=<masked>"),
        ("ppp secret=Hunter2", "ppp secret=<masked>"),
        (" key-string Hunter2", "key-string <masked>"),
        ("standby 1 authentication text Hunter2", "standby 1 authentication text <masked>"),
        ("snmp-server user u g v3 auth sha Hunter2 priv aes 128 Hunter3", "snmp-server user u g v3 auth <masked>"),
        ("description text only", "description text only"),
    ],
)
def test_mask_text(text, expected):
    assert mask_text(text, 160) == expected


def test_describe_failure_is_one_safe_line():
    line = describe_failure({"phase": "replay", "command_index": 2, "command_total": 5, "command": "host-name x"})
    assert line == "phase=replay command=2/5 sent='host-name x'"
    assert describe_failure({"phase": "bogus"}) == ""


def test_unknown_phases_and_login_credentials_never_survive_the_filter():
    assert failure_context({"phase": "prepare-vpn"}) == {}
    login = {"phase": "login", "attempts": 3, "credential": "factory", "password": "x"}
    assert failure_context(login) == {"phase": "login"}
