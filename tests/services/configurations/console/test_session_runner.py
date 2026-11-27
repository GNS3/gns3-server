"""Console recovery decisions after a configuration session."""

from types import SimpleNamespace

import pytest

from gns3server.services.configurations.console.session_runner import _needs_recovery
from gns3server.services.configurations.shared.errors import ConfigurationError


def lease(written=10, probe_only=False, error=None):
    return SimpleNamespace(written_bytes=written, probe_only=probe_only, error=error)


@pytest.mark.parametrize(
    "session,error,failure,complete,expected",
    [
        (lease(), None, None, True, False),  # finished: nothing to recover
        (lease(written=0), None, "console_capture_failed", False, False),  # never wrote to the guest
        (lease(), None, "configuration_apply_failed", False, True),  # wrote, then failed
        (lease(probe_only=True), None, "console_not_ready", False, False),  # a preflight refusal
        (lease(probe_only=False), None, "console_not_ready", False, True),  # the same code after real input
        (
            lease(),
            ConfigurationError("console_authentication_failed", console_reusable=True),
            "console_authentication_failed",
            False,
            False,
        ),
        (lease(), ConfigurationError("console_authentication_failed"), "console_authentication_failed", False, True),
    ],
    ids=[
        "complete",
        "no_output",
        "failed_after_input",
        "preflight",
        "late_not_ready",
        "confirmed_login",
        "unconfirmed_login",
    ],
)
def test_the_console_needs_recovery_only_after_an_uncertain_session(session, error, failure, complete, expected):
    assert _needs_recovery(session, error, failure, complete) is expected
