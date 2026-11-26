"""Console recipes: one ``config_<device>.py`` module per platform, each declaring a ``PLATFORM``.

Register a module here. Imports stay lazy so recipes can import the shared contracts in either order.
"""

from functools import cache
from importlib import import_module

RECIPE_MODULES = (
    "config_ios",
    "config_nxos",
    "config_asa",
    "config_iosxr",
    "config_mikrotik",
    "config_viptela",
    "config_panos",
    "config_eos",
    "config_junos",
)


@cache
def get_recipe_modules():
    return tuple(import_module(f"{__name__}.{name}") for name in RECIPE_MODULES)
