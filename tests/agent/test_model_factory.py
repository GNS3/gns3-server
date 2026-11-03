"""
Tests for the model factory request controls.

A silent provider connection used to wait for the OpenAI SDK default of
600s before the SDK retried. The factory now sets a shorter timeout and
a bounded retry count for the providers that accept them, and keeps usage
metadata in streaming mode.
"""

from typing import Any

import pytest

from gns3server.agent.gns3_copilot.agent import model_factory


def _config(**overrides: Any) -> dict[str, Any]:
    config = {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "api_key": "test-key",
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0.3,
    }
    config.update(overrides)
    return config


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture the kwargs passed to init_chat_model."""
    box: dict[str, Any] = {}

    def fake_init_chat_model(**kwargs: Any) -> object:
        box.update(kwargs)
        return object()

    monkeypatch.setattr(model_factory, "init_chat_model", fake_init_chat_model)
    return box


def test_base_model_gets_timeout_and_bounded_retries(captured: dict[str, Any]) -> None:
    model_factory.create_base_model(_config())

    assert captured["timeout"] == model_factory.DEFAULT_REQUEST_TIMEOUT_S
    assert captured["max_retries"] == model_factory.DEFAULT_MAX_RETRIES
    assert captured["stream_usage"] is True
    # DeepSeek thinking stays disabled
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_request_timeout_from_config_wins(captured: dict[str, Any]) -> None:
    model_factory.create_base_model(_config(request_timeout="60"))
    assert captured["timeout"] == 60.0


@pytest.mark.parametrize("value", ["abc", 0, -5, None])
def test_invalid_request_timeout_falls_back(captured: dict[str, Any], value: Any) -> None:
    model_factory.create_base_model(_config(request_timeout=value))
    assert captured["timeout"] == model_factory.DEFAULT_REQUEST_TIMEOUT_S


def test_providers_without_request_controls_get_none(captured: dict[str, Any]) -> None:
    """Ollama and google-genai reject these kwargs at construction."""
    model_factory.create_base_model(_config(provider="ollama", base_url="http://localhost:11434"))

    assert "timeout" not in captured
    assert "max_retries" not in captured
    assert "stream_usage" not in captured


def test_title_model_gets_the_same_controls(captured: dict[str, Any]) -> None:
    model_factory.create_title_model(_config())

    assert captured["timeout"] == model_factory.DEFAULT_REQUEST_TIMEOUT_S
    assert captured["max_retries"] == model_factory.DEFAULT_MAX_RETRIES
    assert captured["stream_usage"] is True
