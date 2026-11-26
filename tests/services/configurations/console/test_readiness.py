"""When a console counts as ready for automation: an actionable prompt, nothing booting, a quiet stream."""

import asyncio
from types import SimpleNamespace

import pytest

from gns3server.services.configurations.console.platforms import get_platform
from gns3server.services.configurations.console.session_runner import wait_for_console_ready
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.failure_context import describe_failure
from gns3server.utils.asyncio.console_lease import ConsoleReadiness

SYSLOG = (
    "switch login:\r\n"
    "switch vdaemon[812]: %Notification: control-connection-state-change\r\n"
    "switch ompd[900]: %Notification: omp-peer-state-change\r\n"
)


def test_a_prompt_followed_by_other_output_is_not_ready():
    assert not get_platform("cisco_nxos").console_ready(SYSLOG)
    assert not get_platform("cisco_ios_telnet").console_ready("Router#\r\n%LINK-3-UPDOWN: Interface changed\r\n")


def test_only_the_last_line_decides():
    platform = get_platform("cisco_nxos")
    assert platform.console_ready("noise\r\nswitch#")
    assert platform.console_ready("switch login:")
    assert not platform.console_ready("Starting services")


@pytest.mark.parametrize("boot_line", ["[    5.123456] kernel: starting service", "Starting vdaemon..."])
def test_boot_output_after_a_prompt_keeps_the_console_not_ready(boot_line):
    assert not get_platform("cisco_nxos").console_ready(f"switch login:\r\n{boot_line}\r\n")


@pytest.mark.parametrize("driver", ["cisco_asa", "cisco_xe", "cisco_ios_telnet"])
@pytest.mark.parametrize("loader", ["rommon 1 >", "loader >", "grub>", "boot>"])
def test_loader_prompts_are_never_ready(driver, loader):
    platform = get_platform(driver)
    assert not platform.console_ready(f"Booting...\r\n{loader}")
    assert not platform.console_ready(f"{loader}\r\nsome noise\r\n")


@pytest.mark.asyncio
async def test_the_stream_never_settles_while_output_keeps_arriving():
    observed = ConsoleReadiness()
    observed.feed_data(b"Router#")

    async def chatter():
        for _ in range(60):
            await asyncio.sleep(0.02)
            observed.feed_data(b"Router#")

    task = asyncio.create_task(chatter())
    with pytest.raises(TimeoutError):
        await observed.wait_for(lambda text: text.endswith("#"), 0.4, settle_seconds=0.2)
    task.cancel()


@pytest.mark.asyncio
async def test_a_startup_wait_does_not_accept_a_prompt_followed_by_syslog():
    readiness = ConsoleReadiness()
    readiness.feed_data(SYSLOG.encode())
    node = SimpleNamespace(
        status="started",
        console_type="telnet",
        _configuration_console_proxy=SimpleNamespace(_console_readiness=readiness),
        _process=object(),
    )
    with pytest.raises(ConfigurationError, match="configuration_apply_timeout"):
        await wait_for_console_ready(node, "cisco_nxos", 1.3)


@pytest.mark.asyncio
async def test_readiness_timeout_reports_the_ready_phase_with_the_last_console_lines(caplog):
    readiness = ConsoleReadiness()
    readiness.feed_data(b"\x1b[0mnoise\r\nrebooting\r\nPress any key password: hunter2\r\n\r\n")
    node = SimpleNamespace(
        name="vsmart-2",
        status="started",
        console_type="telnet",
        _configuration_console_proxy=SimpleNamespace(_console_readiness=readiness),
        _process=object(),
    )
    with pytest.raises(ConfigurationError, match="configuration_apply_timeout") as caught:
        await wait_for_console_ready(node, "cisco_ios_telnet", 0.2)
    assert caught.value.context == {"phase": "ready", "device_error": "rebooting | Press any key <masked>"}
    assert "hunter2" not in describe_failure(caught.value.context)
    assert "vsmart-2" in caplog.text and "rebooting" in caplog.text
