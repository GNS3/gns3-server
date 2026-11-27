"""Configuration comparison and compute read-back confirmation of startup restore."""

from types import SimpleNamespace

import pytest

from gns3server.compute.configurations import ConfigurationService
from gns3server.schemas.configurations import ApplyOptions, ConsoleCredentials, Engine
from gns3server.services.configurations.console.verification import restore_verified, scoped_lines
from gns3server.services.configurations.shared.errors import ConfigurationError

UPLOADED = """hostname asav
interface GigabitEthernet0/0
 nameif outside
 security-level 0
"""

CAPTURED = """ASA Version 9.18(4)
hostname asav
interface GigabitEthernet0/0
 nameif outside
 security-level 0
: end
"""

FACTORY = """ASA Version 9.18(4)
hostname ciscoasa
interface GigabitEthernet0/0
 shutdown
 no nameif
: end
"""


def console_node():
    return SimpleNamespace(
        id="node",
        status="started",
        console_type="telnet",
        _process=object(),
        _configuration_console_proxy=object(),
    )


def options(**values):
    return ApplyOptions(
        **{
            "device_type": "cisco_asa",
            "content": UPLOADED,
            "credentials": ConsoleCredentials(),
            "wait_ready": True,
            **values,
        }
    )


def patches(monkeypatch, captures):
    """Serve the replay and the read-back from one console entry point."""
    replays = []

    async def console(node, credentials, *, device_type="cisco_ios_telnet", deadline=25, backup=False, **rest):
        if rest.get("content") is not None:
            replays.append({"content": rest["content"], "wait_ready": rest.get("wait_ready")})
            return b"applied\n"
        assert backup is True
        value = captures.pop(0) if captures else ConfigurationError("console_unavailable")
        if isinstance(value, Exception):
            raise value
        return value

    async def ready(node, device_type, deadline, *, startup):
        assert startup is True

    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", console)
    monkeypatch.setattr("gns3server.compute.configurations.wait_for_console_ready", ready)
    return replays


@pytest.mark.asyncio
async def test_a_readback_mismatch_does_not_authorize_another_replay(monkeypatch):
    node = console_node()
    replays = patches(monkeypatch, [FACTORY.encode(), CAPTURED.encode()])
    with pytest.raises(ConfigurationError, match="configuration_apply_unverified"):
        await ConfigurationService(node, Engine.qemu).apply(options())
    assert [entry["content"] for entry in replays] == [UPLOADED]


@pytest.mark.asyncio
@pytest.mark.parametrize("captured", [FACTORY.encode(), b"ASA Version 9.18(4)\nhostname asav\n: end\n"])
async def test_restore_is_not_reported_applied_when_the_guest_never_shows_it(monkeypatch, captured):
    node = console_node()
    patches(monkeypatch, [captured, captured])
    with pytest.raises(ConfigurationError, match="configuration_apply_unverified"):
        await ConfigurationService(node, Engine.qemu).apply(options())


@pytest.mark.asyncio
async def test_confirmed_restore_is_replayed_once(monkeypatch):
    node = console_node()
    replays = patches(monkeypatch, [CAPTURED.encode()])
    await ConfigurationService(node, Engine.qemu).apply(options())
    assert len(replays) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [ConfigurationError("console_busy"), ConfigurationError("console_not_ready"), TimeoutError()]
)
async def test_unreadable_guest_reports_verification_unavailable(monkeypatch, failure):
    node = console_node()
    replays = patches(monkeypatch, [failure, failure])
    with pytest.raises(ConfigurationError, match="configuration_verification_unavailable"):
        await ConfigurationService(node, Engine.qemu).apply(options())
    assert len(replays) == 1


@pytest.mark.asyncio
async def test_live_apply_does_not_read_the_configuration_back(monkeypatch):
    node = console_node()
    replays = patches(monkeypatch, [])
    await ConfigurationService(node, Engine.qemu).apply(options(wait_ready=False, running=True))
    assert len(replays) == 1


@pytest.mark.asyncio
async def test_platforms_without_a_comparable_capture_are_not_verified(monkeypatch):
    node = console_node()
    replays = patches(monkeypatch, [])
    uploaded = "# 2026-11-16 by RouterOS 6.46.5\n/system identity set name=r1\n/ip dns set servers=1.1.1.1\n"
    await ConfigurationService(node, Engine.qemu).apply(
        ApplyOptions(device_type="mikrotik_routeros", content=uploaded, wait_ready=True)
    )
    assert len(replays) == 1


def test_framing_and_indentation_do_not_affect_comparison():
    assert list(scoped_lines("!comment\n\n  nameif   outside \n: end\nend\n")) == [("nameif outside",)]


def test_small_documents_require_matching_readback():
    assert restore_verified("hostname asav\n", FACTORY) == (False, 0.0)
    assert restore_verified("hostname asav\n", CAPTURED) == (True, 1.0)


def test_commands_on_another_interface_do_not_verify():
    uploaded = "interface Ethernet1\n description expected\n no shutdown\n"
    captured = "interface Ethernet1\n shutdown\ninterface Ethernet2\n description expected\n no shutdown\n"
    assert restore_verified(uploaded, captured) == (False, 1 / 3)


def test_one_reformatted_line_is_tolerated_in_a_short_upload():
    uploaded = "hostname R1\nenable secret cisco\nip domain name lab.local\n"
    captured = "hostname R1\nenable secret 9 $14$hash\nip domain name lab.local\n"
    assert restore_verified(uploaded, captured)[0] is True


CAPTURE = "hostname R1\n!\ninterface Gi1\n shutdown\n ip address 1.1.1.1 255.255.255.0\n!\ninterface Gi2\n description x\n!\nend\n"


def test_an_unindented_text_is_placed_under_the_parent_lines_of_the_capture():
    assert restore_verified("hostname R1\ninterface Gi2\ndescription x\n", CAPTURE) == (True, 1.0)


def test_an_unindented_command_on_another_interface_does_not_verify():
    assert restore_verified("interface Gi1\ndescription x\n", CAPTURE) == (False, 0.5)


def test_a_negated_default_is_not_held_against_the_capture_but_a_contradiction_is():
    assert restore_verified("interface Gi2\n no shutdown\n description x\n", CAPTURE) == (True, 1.0)
    assert restore_verified("interface Gi1\n no shutdown\n", CAPTURE) == (False, 0.5)


def test_a_text_of_only_unprovable_commands_has_nothing_to_compare():
    assert restore_verified("no ip domain-lookup\n", CAPTURE) == (None, None)


BGP_CAPTURE = """router bgp 65000
 neighbor 192.0.2.2 remote-as 65001
 !
 address-family ipv4
  network 192.0.2.0 mask 255.255.255.0
  redistribute connected
 exit-address-family
 !
 address-family ipv6
  network 2001:DB8::/32
 exit-address-family
 redistribute static
!
interface Gi1
 description x
end
"""


@pytest.mark.parametrize(
    "uploaded",
    [
        "router bgp 65000\naddress-family ipv4\nnetwork 192.0.2.0 mask 255.255.255.0\n",
        # The next family and the parent block are entered without an exit line.
        "router bgp 65000\naddress-family ipv4\nredistribute connected\naddress-family ipv6\nnetwork 2001:DB8::/32\n"
        "neighbor 192.0.2.2 remote-as 65001\ninterface Gi1\ndescription x\n",
        "router bgp 65000\naddress-family ipv4\nredistribute connected\nexit-address-family\nredistribute static\n",
    ],
    ids=["nested_block", "next_blocks", "explicit_exit"],
)
def test_an_unindented_text_follows_nested_blocks_of_the_capture(uploaded):
    assert restore_verified(uploaded, BGP_CAPTURE) == (True, 1.0)


@pytest.mark.parametrize(
    "uploaded",
    [
        "router bgp 65000\naddress-family ipv6\nnetwork 192.0.2.0 mask 255.255.255.0\n",
        # After the exit the command belongs to the router block, where the capture does not have it.
        "router bgp 65000\naddress-family ipv4\nexit-address-family\nredistribute connected\n",
    ],
    ids=["other_family", "after_exit"],
)
def test_an_unindented_command_in_the_wrong_nested_block_does_not_verify(uploaded):
    assert restore_verified(uploaded, BGP_CAPTURE)[0] is False
