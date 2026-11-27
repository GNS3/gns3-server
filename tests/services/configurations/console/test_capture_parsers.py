"""Console capture parsers and ASA pager handling."""

import pytest

from gns3server.services.configurations.console.platforms import get_platform
from gns3server.services.configurations.console.recipes.config_asa import ASAPager
from tests.support.configurations import (
    CONFIG,
    PANOS_CONFIG,
    PLATFORM_CASES,
    VENDORS,
    asa_configuration,
    ios_configuration,
)


def test_ios_parser_requires_complete_output_and_ignores_prompt_inside_banner():
    prefix = "show running-config\nBuilding configuration...\nCurrent configuration : 100 bytes\n\n"
    assert ios_configuration(prefix + CONFIG.decode() + "R1#", "R1#") == CONFIG
    assert ios_configuration(prefix + "version 15.9\nbanner motd ^C\nend\nR1#", "R1#") is None
    assert ios_configuration(prefix + "version 15.9\nhostname R1\nR1#", "R1#") is None
    assert ios_configuration(prefix + CONFIG.decode() + "OTHER#", "R1#") is None


@pytest.mark.parametrize("driver,parser,prompt,header,content,_commands", PLATFORM_CASES)
def test_platform_parser_requires_complete_platform_framing(driver, parser, prompt, header, content, _commands):
    framing = "show running-config\r\n" + header.decode()
    transcript = framing + content.decode().replace("\n", "\r\n")
    assert parser(transcript + prompt.decode() + "\r\n", prompt.decode()) == content
    assert parser(transcript, prompt.decode()) is None
    assert parser(transcript + "OTHER#", prompt.decode()) is None
    assert parser("show running-config\r\n% Permission denied\r\n" + prompt.decode(), prompt.decode()) is None
    assert (
        parser(
            framing
            + content.decode()
            .replace("version ", "missing-version ")
            .replace("ASA Version ", "missing-ASA ")
            .replace("!! IOS XR Configuration ", "missing-XR ")
            + prompt.decode(),
            prompt.decode(),
        )
        is None
    )
    if driver != "cisco_asa":
        inside_banner = transcript.split("private-banner")[0]
        assert parser(inside_banner, prompt.decode()) is None
    if driver in ("cisco_asa", "cisco_xr"):
        without_end = "\n".join(content.decode().split("\n")[:-2]) + "\n"
        assert parser(framing + without_end + prompt.decode(), prompt.decode()) is None


@pytest.mark.parametrize("marker", ["<--- More --->", "---More---", "--More--"])
@pytest.mark.parametrize("erase", ["backspace", "carriage-return", "ansi"])
def test_asa_pager_handles_fragmented_markers_and_erasure_without_losing_indentation(marker, erase):
    pager = ASAPager()
    first = "show running-config\r\nASA Version 9.19(1)\r\nhostname ASAv\r\n"
    last = "interface GigabitEthernet0/0\r\n  description keep indentation\r\n: end\r\nASAv#"
    requests = sum(pager.feed(char) for char in first + marker)
    assert requests == 1
    erasure = {
        "backspace": "\b" * len(marker) + " " * len(marker) + "\b" * len(marker),
        "carriage-return": "\r" + " " * len(marker) + "\r",
        "ansi": "\x1b[2K\r",
    }[erase]
    requests += sum(pager.feed(char) for char in erasure + last)
    assert requests == 1
    assert pager.buffer == first + last
    assert asa_configuration(pager.buffer, "ASAv#") == (
        b"ASA Version 9.19(1)\nhostname ASAv\ninterface GigabitEthernet0/0\n  description keep indentation\n: end\n"
    )


def test_asa_pager_does_not_treat_banner_text_as_a_pager_or_repeat_continuations():
    pager = ASAPager()
    text = "ASA Version 9.19(1)\r\nbanner motd <--- More --->"
    assert not pager.feed(text)
    assert pager.buffer == text
    assert pager.feed("\r\n<--- More --->")
    for _ in range(10):
        assert not pager.feed("")


@pytest.mark.parametrize("driver,prompt,content", VENDORS)
def test_vendor_export_requires_platform_content_and_completed_prompt(driver, prompt, content):
    transcript = "capture command\r\n" + content.replace("\n", "\r\n")
    assert get_platform(driver).parser(transcript + prompt, prompt) == content.encode()
    assert get_platform(driver).parser(transcript, prompt) is None
    assert get_platform(driver).parser("permission denied\r\n" + prompt, prompt) is None


def test_panos_a_repeated_final_prompt_still_completes_the_capture():
    text = f'<response status="success"><result>{PANOS_CONFIG}</result></response>\r\nadmin@PA-VM> admin@PA-VM> '
    assert (
        get_platform("paloalto_panos").parser(text, "admin@PA-VM>")
        == ('<?xml version="1.0"?>\n' + PANOS_CONFIG + "\n").encode()
    )


@pytest.mark.parametrize(
    "transcript",
    [
        "show config running\r\n",
        '<response status="success"><result><config version="11.2.0"><a></config></result></response>\r\nadmin@PA-VM> ',
        '<response status="error"><result>no</result></response>\r\nadmin@PA-VM> ',
        '<response status="success"><result><config/></result></response>\r\n<response status="success"><result><config/></result></response>\r\nadmin@PA-VM> ',
    ],
)
def test_panos_incomplete_or_ambiguous_output_is_not_a_capture(transcript):
    assert get_platform("paloalto_panos").parser(transcript, "admin@PA-VM>") is None


@pytest.mark.parametrize(
    "transcript",
    [
        "show running-config\r\n! Command: show running-config\r\nno aaa root\r\n",
        "! Command: show running-config\r\nbanner login\r\nhello\r\nend\r\nlocalhost#",
        "! Command: show running-config\r\ninterface Ethernet1\r\n!\r\nlocalhost#",
    ],
)
def test_eos_incomplete_output_is_not_a_capture(transcript):
    assert get_platform("arista_eos").parser(transcript, "localhost#") is None


def test_eos_banners_are_complete_only_when_closed_by_eof():
    parse = get_platform("arista_eos").parser
    closed = "! Command: show running-config\r\nbanner login\r\nhello\r\nEOF\r\n!\r\nend\r\nlocalhost#"
    assert parse(closed, "localhost#") == b"! Command: show running-config\nbanner login\nhello\nEOF\n!\nend\n"


@pytest.mark.parametrize(
    "transcript",
    [
        "show configuration | no-more\r\n",
        "## Last commit: x\r\nversion 23.2R1.13;\r\nsystem {\r\n    host-name vsrx;\r\nroot> ",
        "version 23.2R1.13;\r\nsystem {\r\n    login {\r\n}\r\nroot> ",
        "## Last commit: x\r\nsystem {\r\n    host-name vsrx;\r\n}\r\n\r\nroot> ",
    ],
)
def test_junos_incomplete_output_is_not_a_capture(transcript):
    assert get_platform("juniper_junos").parser(transcript, "root>") is None
