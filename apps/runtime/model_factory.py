"""Construct Strands models behind one provider-neutral project seam."""

from __future__ import annotations

import os
from typing import Protocol

from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel, Model

from packages.domain.errors import ProviderConfigurationError

from .recorded_model import RecordedManifestModel
from .runtime_settings import RuntimeSettings
from .strands_tools import GovernedInvocationContext


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def bedrock_mantle_base_url(region: str) -> str:
    return f"https://bedrock-mantle.{region}.api.aws/v1"


class ManifestModelFactory(Protocol):
    def validate(self, settings: RuntimeSettings) -> None:
        """Validate local provider prerequisites without invoking a model."""

    def create(
        self,
        settings: RuntimeSettings,
        context: GovernedInvocationContext,
    ) -> Model:
        """Create a fresh model for one isolated role invocation."""


class DefaultManifestModelFactory:
    def validate(self, settings: RuntimeSettings) -> None:
        settings.validate()
        if settings.model_provider == "openrouter":
            self._openrouter_api_key()
            self._openai_model_class()
        elif settings.model_provider == "bedrock_mantle":
            self._bedrock_mantle_api_key()
            self._openai_model_class()

    def create(
        self,
        settings: RuntimeSettings,
        context: GovernedInvocationContext,
    ) -> Model:
        self.validate(settings)
        if settings.model_provider == "recorded":
            return RecordedManifestModel(context, model_id=settings.model_id)
        if settings.model_provider == "openrouter":
            openai_model = self._openai_model_class()
            return openai_model(
                client_args={
                    "api_key": self._openrouter_api_key(),
                    "base_url": OPENROUTER_BASE_URL,
                    "max_retries": 0,
                    "timeout": settings.timeout_seconds,
                },
                model_id=settings.model_id,
                params={
                    "max_tokens": settings.max_output_tokens,
                    "temperature": 0,
                },
            )
        if settings.model_provider == "bedrock_mantle":
            openai_model = self._openai_model_class()
            return openai_model(
                client_args={
                    "api_key": self._bedrock_mantle_api_key(),
                    "base_url": bedrock_mantle_base_url(settings.bedrock_region),
                    "max_retries": 0,
                    "timeout": settings.timeout_seconds,
                },
                model_id=settings.model_id,
                params={
                    "max_tokens": settings.max_output_tokens,
                    "temperature": 0,
                },
            )
        if settings.model_provider == "bedrock":
            return BedrockModel(
                model_id=settings.model_id,
                region_name=settings.bedrock_region,
                max_tokens=settings.max_output_tokens,
                temperature=0,
                boto_client_config=BotocoreConfig(
                    connect_timeout=min(5, settings.timeout_seconds),
                    read_timeout=settings.timeout_seconds,
                    retries={"total_max_attempts": 1, "mode": "standard"},
                ),
            )
        raise ProviderConfigurationError(
            f"Model provider {settings.model_provider!r} is not supported."
        )

    @staticmethod
    def _openrouter_api_key() -> str:
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ProviderConfigurationError(
                "OpenRouter mode requires OPENROUTER_API_KEY in the process environment."
            )
        return key

    @staticmethod
    def _bedrock_mantle_api_key() -> str:
        key = os.environ.get("BEDROCK_MANTLE_API_KEY", "").strip()
        if not key:
            raise ProviderConfigurationError(
                "Bedrock Mantle mode requires BEDROCK_MANTLE_API_KEY in the process environment."
            )
        return key

    @staticmethod
    def _openai_model_class():
        try:
            from strands.models.openai import OpenAIModel
        except ModuleNotFoundError as exc:
            if exc.name == "openai":
                raise ProviderConfigurationError(
                    "The selected OpenAI-compatible provider requires its project optional dependency."
                ) from exc
            raise
        return OpenAIModel
