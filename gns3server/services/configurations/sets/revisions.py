"""Small, invalidation-aware revision cache for status polling."""

import stat
import threading
from collections import OrderedDict

from gns3server.services.configurations.shared.safe_io import linked

_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_MAX_ENTRIES = 32


def _identity(path):
    try:
        value = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or linked(path):
        return None
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def read_revision(path, load):
    """Read a validated manifest once per file identity, under its store lock."""
    path = path.absolute()
    before = _identity(path)
    with _CACHE_LOCK:
        cached = _CACHE.get(path)
        if before is not None and cached is not None and before == cached[0]:
            _CACHE.move_to_end(path)
            return cached[1]
    revision = load()
    if before is not None and before == _identity(path):
        with _CACHE_LOCK:
            _CACHE[path] = (before, revision)
            _CACHE.move_to_end(path)
            if len(_CACHE) > _MAX_ENTRIES:
                _CACHE.popitem(last=False)
    return revision
