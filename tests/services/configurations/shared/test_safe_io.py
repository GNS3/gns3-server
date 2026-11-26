import os

import pytest

from gns3server.services.configurations.shared import safe_io
from gns3server.services.configurations.shared.errors import ConfigurationError


@pytest.mark.skipif(not hasattr(os, "O_DIRECTORY"), reason="descriptor-relative writes need POSIX")
def test_atomic_write_takes_the_descriptor_relative_path_on_posix(tmp_path, monkeypatch):
    taken = []
    original = safe_io._atomic_write_at
    monkeypatch.setattr(safe_io, "_atomic_write_at", lambda *args: (taken.append(args[1]), original(*args)))
    safe_io.atomic_write(str(tmp_path), "etc/network/interfaces", "auto eth0\n")
    assert taken == [("etc", "network", "interfaces")]
    assert (tmp_path / "etc/network/interfaces").read_text() == "auto eth0\n"


def test_regular_file_reader_is_bounded_and_rejects_links(tmp_path):
    file = tmp_path / "file"
    file.write_bytes(b"12345")
    assert safe_io.stable_read(str(tmp_path), file, 5) == b"12345"
    with pytest.raises(ConfigurationError, match="configuration_too_large"):
        safe_io.stable_read(str(tmp_path), file, 4)
    (tmp_path / "link").symlink_to(file)
    with pytest.raises(ConfigurationError, match="unsafe_configuration_path"):
        safe_io.stable_read(str(tmp_path), tmp_path / "link", 5)
