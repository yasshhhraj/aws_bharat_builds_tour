import pytest

from apps.runtime.model_factory import (
    OPENROUTER_BASE_URL,
    DefaultManifestModelFactory,
    bedrock_mantle_base_url,
)
from apps.runtime.recorded_model import RecordedManifestModel
from apps.runtime.runtime_settings import RuntimeSettings
from packages.domain.errors import ProviderConfigurationError


def test_recorded_factory_returns_the_offline_model():
    context = object()
    settings = RuntimeSettings("strands", "recorded", "manifest-recorded-v1")

    model = DefaultManifestModelFactory().create(settings, context)  # type: ignore[arg-type]

    assert isinstance(model, RecordedManifestModel)
    assert model.context is context


def test_openrouter_requires_a_process_environment_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = RuntimeSettings("strands", "openrouter", "openrouter/free")

    with pytest.raises(ProviderConfigurationError, match="requires OPENROUTER_API_KEY"):
        DefaultManifestModelFactory().validate(settings)


def test_openrouter_factory_uses_fixed_endpoint_and_bounded_client(monkeypatch):
    captured = {}

    class FakeOpenAIModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-test-value")
    monkeypatch.setattr(
        DefaultManifestModelFactory,
        "_openai_model_class",
        staticmethod(lambda: FakeOpenAIModel),
    )
    settings = RuntimeSettings(
        "strands",
        "openrouter",
        "openrouter/free",
        timeout_seconds=30,
        max_output_tokens=512,
    )

    model = DefaultManifestModelFactory().create(settings, object())  # type: ignore[arg-type]

    assert isinstance(model, FakeOpenAIModel)
    assert captured["model_id"] == "openrouter/free"
    assert captured["client_args"] == {
        "api_key": "secret-test-value",
        "base_url": OPENROUTER_BASE_URL,
        "max_retries": 0,
        "timeout": 30,
    }
    assert captured["params"] == {"max_tokens": 512, "temperature": 0}
    assert "secret-test-value" not in repr(settings.describe())


def test_bedrock_factory_is_explicitly_region_bound_without_invocation(monkeypatch):
    captured = {}

    def fake_bedrock_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("apps.runtime.model_factory.BedrockModel", fake_bedrock_model)
    settings = RuntimeSettings(
        "strands",
        "bedrock",
        "us.amazon.nova-2-lite-v1:0",
        timeout_seconds=20,
        max_output_tokens=768,
        bedrock_region="us-east-1",
    )

    model = DefaultManifestModelFactory().create(settings, object())  # type: ignore[arg-type]

    assert model is not None
    assert captured["model_id"] == "us.amazon.nova-2-lite-v1:0"
    assert captured["region_name"] == "us-east-1"
    assert captured["max_tokens"] == 768
    assert captured["boto_client_config"].retries["total_max_attempts"] == 1


def test_bedrock_mantle_requires_a_dedicated_process_environment_key(monkeypatch):
    monkeypatch.delenv("BEDROCK_MANTLE_API_KEY", raising=False)
    settings = RuntimeSettings(
        "strands", "bedrock_mantle", "qwen.qwen3-coder-next"
    )

    with pytest.raises(ProviderConfigurationError, match="BEDROCK_MANTLE_API_KEY"):
        DefaultManifestModelFactory().validate(settings)


def test_bedrock_mantle_uses_region_endpoint_and_openai_adapter(monkeypatch):
    captured = {}

    class FakeOpenAIModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("BEDROCK_MANTLE_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(
        DefaultManifestModelFactory,
        "_openai_model_class",
        staticmethod(lambda: FakeOpenAIModel),
    )
    settings = RuntimeSettings(
        "strands",
        "bedrock_mantle",
        "qwen.qwen3-coder-next",
        timeout_seconds=45,
        max_output_tokens=512,
        bedrock_region="us-east-1",
    )

    model = DefaultManifestModelFactory().create(settings, object())  # type: ignore[arg-type]

    assert isinstance(model, FakeOpenAIModel)
    assert captured["model_id"] == "qwen.qwen3-coder-next"
    assert captured["client_args"] == {
        "api_key": "synthetic-test-key",
        "base_url": bedrock_mantle_base_url("us-east-1"),
        "max_retries": 0,
        "timeout": 45,
    }
    assert captured["params"] == {"max_tokens": 512, "temperature": 0}
    assert "synthetic-test-key" not in repr(settings.describe())
