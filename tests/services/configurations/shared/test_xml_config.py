"""The XML check shared by the PAN-OS capture and boot media."""

import pytest

from gns3server.services.configurations.shared.xml_config import parse_config, serialize

DOCUMENT = '<config version="11.2.0"><devices><entry name="localhost.localdomain"/></devices></config>'


def test_a_config_document_is_parsed_and_serialized_with_a_declaration():
    root = parse_config(DOCUMENT)
    assert root is not None and root.get("version") == "11.2.0"
    assert serialize(root).startswith(b'<?xml version="1.0"?>\n<config version="11.2.0">') and serialize(root).endswith(
        b"\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not xml",
        "<config><unclosed></config>",
        "<other/>",
        "<config/><config/>",
        '<!DOCTYPE config [<!ENTITY x "y">]><config>&x;</config>',
        "<config><?php echo 1 ?></config>",
        "<config>" + "<a>" * 100 + "</a>" * 100 + "</config>",
    ],
)
def test_text_that_is_not_one_plain_config_document_is_refused(text):
    assert parse_config(text) is None


def test_the_xml_declaration_alone_is_allowed():
    assert parse_config('<?xml version="1.0"?><config/>') is not None
