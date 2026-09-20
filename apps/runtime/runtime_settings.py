"""Validated agent-runtime configuration with safe local defaults."""

from __future__ import annotations

from dataclasses import dataclass
import os

from packages.domain.errors import RuntimeConfigurationError


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    runtime_mode: str = "legacy"
    model_provider: str = "deterministic"
    model_id: str = "manifest-deterministic-v1"
    max_turns: int = 8
    timeout_seconds: float = 15.0
    max_output_tokens: int = 1_024
    bedrock_region: str = "us-east-1"

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        runtime_mode = os.environ.get("MANIFEST_AGENT_RUNTIME", "legacy").strip().lower()
        default_provider = "recorded" if runtime_mode == "strands" else "deterministic"
        default_model = "manifest-recorded-v1" if runtime_mode == "strands" else "manifest-deterministic-v1"
        try:
            max_turns = int(os.environ.get("MANIFEST_AGENT_MAX_TURNS", "8"))
            timeout_seconds = float(os.environ.get("MANIFEST_AGENT_TIMEOUT_SECONDS", "15"))
            max_output_tokens = int(
                os.environ.get("MANIFEST_MODEL_MAX_OUTPUT_TOKENS", "1024")
            )
        except ValueError as exc:
            raise RuntimeConfigurationError(
                "Agent turn, timeout, and output-token limits must be numeric."
            ) from exc
        settings = cls(
            runtime_mode=runtime_mode,
            model_provider=os.environ.get(
                "MANIFEST_MODEL_PROVIDER", default_provider
            ).strip().lower(),
            model_id=os.environ.get("MANIFEST_MODEL_ID", default_model).strip(),
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            bedrock_region=os.environ.get(
                "MANIFEST_BEDROCK_REGION", "us-east-1"
            ).strip(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.runtime_mode not in {"legacy", "strands"}:
            raise RuntimeConfigurationError(
                f"Agent runtime {self.runtime_mode!r} is not supported."
            )
        if self.runtime_mode == "legacy" and (
            self.model_provider,
            self.model_id,
        ) != ("deterministic", "manifest-deterministic-v1"):
            raise RuntimeConfigurationError(
                "The legacy runtime supports only manifest-deterministic-v1."
            )
        if self.runtime_mode == "strands":
            if self.model_provider not in {
                "recorded",
                "openrouter",
                "bedrock_mantle",
                "bedrock",
            }:
                raise RuntimeConfigurationError(
                    f"Strands model provider {self.model_provider!r} is not supported."
                )
            if not self.model_id:
                raise RuntimeConfigurationError("The selected model ID cannot be empty.")
            if self.model_provider == "recorded" and self.model_id != "manifest-recorded-v1":
                raise RuntimeConfigurationError(
                    "Recorded mode requires model manifest-recorded-v1."
                )
            if self.model_provider in {"bedrock", "bedrock_mantle"} and not self.bedrock_region:
                raise RuntimeConfigurationError(
                    "Bedrock mode requires MANIFEST_BEDROCK_REGION."
                )
        if not 1 <= self.max_turns <= 12:
            raise RuntimeConfigurationError("Agent maximum turns must be between 1 and 12.")
        if not 0 < self.timeout_seconds <= 60:
            raise RuntimeConfigurationError(
                "Agent timeout must be greater than zero and no more than 60 seconds."
            )
        if not 128 <= self.max_output_tokens <= 2_048:
            raise RuntimeConfigurationError(
                "Model maximum output tokens must be between 128 and 2048."
            )

    @property
    def provider_route_kind(self) -> str:
        return (
            "router"
            if self.model_provider == "openrouter"
            and self.model_id == "openrouter/free"
            else "fixed"
        )

    def describe(self) -> dict[str, object]:
        return {
            "runtime_mode": self.runtime_mode,
            "model_provider": self.model_provider,
            "model_id": self.model_id,
            "requested_model_id": self.model_id,
            "resolved_model_id": None,
            "provider_route_kind": self.provider_route_kind,
            "agent_max_turns": self.max_turns,
            "agent_timeout_seconds": self.timeout_seconds,
            "model_max_output_tokens": self.max_output_tokens,
            "provider_fallback_active": False,
        }
