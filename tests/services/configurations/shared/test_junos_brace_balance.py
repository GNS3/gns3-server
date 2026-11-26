"""Brace balance of hierarchical (Junos) configuration text."""

import pytest

from gns3server.services.configurations.shared.junos_brace_balance import has_balanced_braces


@pytest.mark.parametrize(
    "text",
    [
        "system {\n    host-name vsrx;\n}\n",
        'system {\n    login { message "a } b {"; }\n}\n',  # Braces in a quoted string.
        "system {\n    ## stray { in an annotation\n}\n",
        "system {\n    # a { in a hash comment\n}\n",
        "system {\n    /* a { in a block comment\n       } and another { */\n    host-name vsrx;\n}\n",
        'system {\n    login { message "two\\" } quotes"; }\n}\n',  # An escaped quote does not end the string.
        "",
    ],
)
def test_balanced_text_is_accepted(text):
    assert has_balanced_braces(text)


@pytest.mark.parametrize(
    "text",
    [
        "system {\n    login {\n}\n",
        "}\nsystem {\n",
        'system {\n    login { message "open;\n}\n}\n',
        "system {\n    /* never closed\n}\n",
        "system {\n    host-name vsrx; /* x */ }\n}\n",
    ],
)
def test_unbalanced_text_is_refused(text):
    assert not has_balanced_braces(text)
