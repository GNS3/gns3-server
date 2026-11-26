"""Boot media profiles that change the node's own disk before it boots (``prepare_disk``).

ASAv erases the saved startup through a temporary guest. Profiles that only produce media files are covered by
``test_profiles.py``.
"""

import asyncio

import pytest

from gns3server.services.configurations.boot_media.profiles import cisco_asav as asav


class RecoveryGuest:
    def __init__(self, mode="new_password", clone_reboot=False):
        self.stdout = asyncio.StreamReader()
        self.stdin = self
        self.mode, self.clone_reboot = mode, clone_reboot
        self.commands = []
        self.state = "menu"
        self.password = None
        self.returncode = None
        self.terminated = False
        self.feed(self.menu())

    @staticmethod
    def menu():
        return (
            b"GNU GRUB\nwith no configuration load\nThe highlighted entry will be booted automatically in 10 seconds."
        )

    def feed(self, data):
        self.stdout.feed_data(data)

    async def drain(self):
        pass

    def write(self, value):
        self.commands.append(value)
        if self.state == "menu":
            assert value == b"\x1b[B"
            self.state = "selected"
            self.feed(b"Selected: bootflash:/asa.bin with no configuration load")
        elif self.state == "selected":
            assert value == b"\r"
            self.feed(b"Booting 'bootflash:/asa.bin with no configuration load'\n")
            if self.clone_reboot:
                self.clone_reboot = False
                self.state = "menu"
                self.feed(b"clone reboot\n" + self.menu())
            else:
                self.state = "enable"
                self.feed(b"\nciscoasa> ")
        elif self.state == "enable":
            assert value == b"enable\r"
            if self.mode == "privileged":
                self.state = "erase"
                self.feed(b"\nciscoasa# ")
            else:
                self.state = "password"
                self.feed(b"Enter  Password: " if self.mode == "new_password" else b"Password: ")
        elif self.state == "password":
            if self.mode == "new_password":
                self.password = value
                self.state = "repeat"
                self.feed(b"\nRepeat Password: ")
            else:
                assert value == b"\r"
                self.state = "erase"
                self.feed(b"\nciscoasa# ")
        elif self.state == "repeat":
            assert value == self.password
            self.state = "erase"
            self.feed(b"\nciscoasa# ")
        elif self.state == "erase":
            assert value == b"write erase\r"
            self.state = "confirm_erase"
            self.feed(b"Erase configuration in flash memory? [confirm]")
        elif self.state == "confirm_erase":
            assert value == b"\r"
            self.state = "reload"
            self.feed(b"\n[OK]\n\nciscoasa# ")
        elif self.state == "reload":
            assert value == b"reload\r"
            self.state = "save"
            self.feed(b"System config has been modified. Save? [Y]es/[N]o: ")
        elif self.state == "save":
            assert value == b"n\r"
            self.state = "confirm_reload"
            self.feed(b"Proceed with reload? [confirm]")
        elif self.state == "confirm_reload":
            assert value == b"\r"
            self.state = "flushed"
            self.feed(b"Shutting down File system\nRebooting\nGNU GRUB")
        else:
            raise AssertionError("Recovery sent an unexpected command after disk flush")

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.stdout.feed_eof()

    async def wait(self):
        return self.returncode


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["new_password", "empty_password", "privileged"])
@pytest.mark.parametrize("clone_reboot", [False, True])
async def test_native_recovery_erases_and_declines_saving_temporary_configuration(mode, clone_reboot):
    guest = RecoveryGuest(mode, clone_reboot)
    console = asav.RecoveryConsole(guest)
    try:
        await console.erase()
        assert guest.state == "flushed"
        assert guest.commands.count(b"write erase\r") == 1
        assert b"n\r" in guest.commands
        assert b"write memory\r" not in guest.commands
        if guest.password:
            assert len(guest.password.strip()) >= 16
    finally:
        guest.terminate()
        await console.reader


@pytest.mark.asyncio
async def test_recovery_waits_for_complete_menu_before_sending_any_key():
    guest = RecoveryGuest()
    guest.stdout = asyncio.StreamReader()
    guest.feed(b"GNU GRUB\nwith no configuration load")
    console = asav.RecoveryConsole(guest)
    task = asyncio.create_task(console.erase())
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert guest.commands == []
        guest.feed(b"\nThe highlighted entry will be booted automatically in 10 seconds.")
        await task
        assert guest.state == "flushed"
    finally:
        task.cancel()
        guest.terminate()
        await asyncio.gather(task, console.reader, return_exceptions=True)
