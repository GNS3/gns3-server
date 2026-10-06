import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel

from gns3server import schemas
from gns3server.schemas.update import PartialUpdateModel


def _discover_update_models():
    models = {}
    for module_info in pkgutil.walk_packages(schemas.__path__, f"{schemas.__name__}."):
        module = importlib.import_module(module_info.name)
        for name, cls in vars(module).items():
            if inspect.isclass(cls) and issubclass(cls, BaseModel) and name.endswith("Update"):
                models[f"{cls.__module__}.{cls.__qualname__}"] = cls
    return models


UPDATE_MODELS = _discover_update_models()
PARTIAL_UPDATE_MODELS = {k: v for k, v in UPDATE_MODELS.items() if issubclass(v, PartialUpdateModel)}


@pytest.mark.parametrize("model", UPDATE_MODELS.values(), ids=UPDATE_MODELS.keys())
def test_update_schema_publishes_no_defaults(model):
    properties = model.model_json_schema()["properties"]
    assert {name: p["default"] for name, p in properties.items() if p.get("default") is not None} == {}


@pytest.mark.parametrize("model", PARTIAL_UPDATE_MODELS.values(), ids=PARTIAL_UPDATE_MODELS.keys())
def test_partial_update_schema_drops_excluded_fields(model):
    inherited = {field for base in model.__mro__[1:] if hasattr(base, "model_fields") for field in base.model_fields}
    for field in model.update_excluded_fields:
        assert field in inherited
        assert field not in model.model_fields
        assert model.model_validate({field: None}).model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize("model", PARTIAL_UPDATE_MODELS.values(), ids=PARTIAL_UPDATE_MODELS.keys())
def test_partial_update_schema_requires_nothing(model):
    assert model().model_dump() == {}
    assert model().model_dump_json() == "{}"
