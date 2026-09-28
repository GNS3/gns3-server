# NOTE: this patches the standard zipfile module
from . import _zipfile

from zipfile import *
from ._zipfile import (
    ZIP_ZSTANDARD,
    ZSTANDARD_VERSION,
)
