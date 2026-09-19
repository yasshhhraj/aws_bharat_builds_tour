"""Cedar-backed implementation of the Manifest PolicyEngine port."""

from __future__ import annotations

from pathlib import Path

from packages.domain.models import PolicyRequest, PolicySignal, TrajectoryState

from .client import CedarClient, CedarClientError
from .context import build_cedar_request
from .mapping import CedarMappingError, CedarPolicyMetadata


class CedarPolicyEngine:
    name = "cedar"

    def __init__(
        self,
        client: CedarClient,
        *,
        metadata_path: Path,
        expected_policy_version: str = "demo-v1",
        expected_bundle_hash: str | None = None,
    ) -> None:
        self.client = client
        self.metadata = CedarPolicyMetadata(metadata_path)
        self.policy_version = expected_policy_version
        self.expected_bundle_hash = expected_bundle_hash
        self.bundle_hash: str | None = None
        self.schema_hash: str | None = None
        self.cedar_version: str | None = None

    def validate_startup(self) -> None:
        health = self.client.health()
        if (
            health.status != "ready"
            or health.engine != "cedar"
            or health.validation != "passed"
        ):
            raise CedarClientError("Cedar policy service is not ready.")
        if health.policy_version != self.policy_version:
            raise CedarClientError("Cedar policy version does not match configuration.")
        if self.metadata.policy_version != self.policy_version:
            raise CedarMappingError("Cedar metadata version does not match configuration.")
        if self.expected_bundle_hash and health.bundle_hash != self.expected_bundle_hash:
            raise CedarClientError("Cedar policy bundle hash does not match configuration.")
        self.bundle_hash = health.bundle_hash
        self.schema_hash = health.schema_hash
        self.cedar_version = health.cedar_version

    def evaluate(
        self, request: PolicyRequest, state: TrajectoryState
    ) -> tuple[PolicySignal, ...]:
        if self.bundle_hash is None:
            raise CedarClientError("Cedar policy engine was not validated at startup.")
        cedar_request = build_cedar_request(
            request, state, bundle_hash=self.bundle_hash
        )
        response = self.client.authorize(cedar_request)
        if response.request_id != request.request_id:
            raise CedarClientError("Cedar response request ID does not match.")
        if response.policy_version != self.policy_version:
            raise CedarClientError("Cedar response policy version does not match.")
        if response.bundle_hash != self.bundle_hash:
            raise CedarClientError("Cedar response bundle hash does not match.")
        return self.metadata.map_response(response, request, state)

    def describe(self) -> dict[str, object]:
        return {
            "policy_engine": self.name,
            "policy_version": self.policy_version,
            "policy_engine_ready": self.bundle_hash is not None,
            "policy_bundle_hash": self.bundle_hash,
            "policy_schema_hash": self.schema_hash,
            "cedar_runtime_version": self.cedar_version,
            "policy_fallback_active": False,
        }

