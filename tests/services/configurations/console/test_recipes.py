"""Registration of the console recipes and the Netmiko aliases that reuse them."""

from types import SimpleNamespace

import pytest

from gns3server.schemas.configurations import CONSOLE_DEVICE_TYPES, normalize_device_type
from gns3server.services.configurations.console.platforms import get_platform, get_platforms
from gns3server.services.configurations.shared.errors import CaptureFailure


def test_every_public_console_driver_has_a_complete_adapter():
    assert set(get_platforms()) == CONSOLE_DEVICE_TYPES
    for name in CONSOLE_DEVICE_TYPES:
        platform = get_platform(name)
        assert platform.name == name
        assert callable(platform.parser)
        # Viptela, PAN-OS, EOS and Junos are capture-only: their startup is delivered as boot media.
        assert callable(platform.restorer) or name in ("cisco_viptela", "paloalto_panos", "arista_eos", "juniper_junos")
    assert get_platform("cisco_ios") is get_platform("cisco_ios_telnet")


@pytest.mark.parametrize(
    ("netmiko_type", "recipe"),
    [
        # ASAv uses the ASA CLI; Catalyst 8000v and CSR 1000v use the IOS-XE CLI.
        ("cisco_asa", "cisco_asa"),
        ("cisco_asa_ssh", "cisco_asa"),
        ("cisco_asa_telnet", "cisco_asa"),
        ("cisco_xe", "cisco_ios_telnet"),
        ("cisco_xe_ssh", "cisco_ios_telnet"),
        ("cisco_xe_telnet", "cisco_ios_telnet"),
        ("cisco_ios", "cisco_ios_telnet"),
        ("cisco_nxos_telnet", "cisco_nxos"),
        ("cisco_xr_telnet", "cisco_xr"),
        ("paloalto_panos", "paloalto_panos"),
        ("paloalto_panos_telnet", "paloalto_panos"),
        ("arista_eos", "arista_eos"),
        ("arista_eos_telnet", "arista_eos"),
        ("juniper_junos", "juniper_junos"),
        ("juniper_junos_telnet", "juniper_junos"),
    ],
)
def test_netmiko_names_resolve_to_an_existing_recipe(netmiko_type, recipe):
    assert normalize_device_type(netmiko_type) == recipe
    assert recipe in CONSOLE_DEVICE_TYPES
    assert get_platform(netmiko_type).name == recipe


@pytest.mark.parametrize("value", [None, "", "linux", "cisco_xe_serial", "cisco_asa_serial"])
def test_unrelated_netmiko_names_are_not_adopted_as_console_recipes(value):
    assert normalize_device_type(value) not in CONSOLE_DEVICE_TYPES


@pytest.mark.parametrize(
    ("netmiko", "expected"),
    [(None, True), ("", True), ("linux", True), ("linux_telnet", True), ("cisco_ios", False), ("frr", False)],
)
def test_one_rule_says_which_docker_nodes_start_from_the_network_file(netmiko, expected):
    from gns3server.schemas.configurations import docker_network_file

    assert docker_network_file(netmiko) is expected


def test_save_support_is_declared_explicitly_per_platform():
    assert get_platform("cisco_ios").supports_save
    assert get_platform("cisco_nxos").supports_save
    assert get_platform("cisco_asa").supports_save
    assert not get_platform("cisco_xr").supports_save


def test_platform_save_reports_unsupported_without_console_input():
    session = SimpleNamespace(execute=lambda *args, **kwargs: pytest.fail("must not send commands"))
    with pytest.raises(CaptureFailure, match="configuration_save_unsupported"):
        get_platform("cisco_xr").save(session)
