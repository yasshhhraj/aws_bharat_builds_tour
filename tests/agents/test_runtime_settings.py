import pytest

from apps.runtime.runtime_factory import build_runtime_agents
from apps.runtime.runtime_settings import RuntimeSettings
from apps.runtime.strands_agents import StrandsCarrierAgent, StrandsRoleAgent
from packages.domain.errors import RuntimeConfigurationError


def test_strands_recorded_configuration_builds_four_role_adapters():
    settings = RuntimeSettings("strands", "recorded", "manifest-recorded-v1")

    agents = build_runtime_agents(settings)

    assert len(agents) == 4
    assert isinstance(agents[0], StrandsRoleAgent)
    assert isinstance(agents[2], StrandsCarrierAgent)


def test_strands_accepts_explicit_hosted_providers():
    RuntimeSettings("strands", "openrouter", "openrouter/free").validate()
    RuntimeSettings(
        "strands", "bedrock_mantle", "qwen.qwen3-coder-next"
    ).validate()
    RuntimeSettings(
        "strands", "bedrock", "us.amazon.nova-2-lite-v1:0"
    ).validate()


def test_strands_rejects_an_unknown_provider():
    with pytest.raises(RuntimeConfigurationError):
        RuntimeSettings("strands", "implicit", "some-model").validate()


def test_runtime_limits_are_bounded():
    with pytest.raises(RuntimeConfigurationError):
        RuntimeSettings(max_turns=0).validate()
    with pytest.raises(RuntimeConfigurationError):
        RuntimeSettings(timeout_seconds=61).validate()
    with pytest.raises(RuntimeConfigurationError):
        RuntimeSettings(max_output_tokens=127).validate()
    with pytest.raises(RuntimeConfigurationError):
        RuntimeSettings(max_output_tokens=2049).validate()


def test_environment_defaults_are_provider_specific(monkeypatch):
    monkeypatch.setenv("MANIFEST_AGENT_RUNTIME", "strands")
    monkeypatch.delenv("MANIFEST_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("MANIFEST_MODEL_ID", raising=False)

    settings = RuntimeSettings.from_env()

    assert settings.model_provider == "recorded"
    assert settings.model_id == "manifest-recorded-v1"
    assert settings.describe()["provider_fallback_active"] is False
    assert settings.describe()["model_max_output_tokens"] == 1024


def test_openrouter_router_is_disclosed_without_secret(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-appear")
    settings = RuntimeSettings("strands", "openrouter", "openrouter/free")

    description = settings.describe()

    assert description["provider_route_kind"] == "router"
    assert description["requested_model_id"] == "openrouter/free"
    assert description["resolved_model_id"] is None
    assert "must-not-appear" not in repr(description)
