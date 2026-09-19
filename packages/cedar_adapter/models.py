"""Typed transport contracts for the local Cedar PDP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CedarAuthorizationRequest:
    request_id: str
    principal: str
    action: str
    resource: str
    context: dict[str, Any]
    entities: list[dict[str, Any]]
    policy_version: str
    bundle_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "principal": self.principal,
            "action": self.action,
            "resource": self.resource,
            "context": self.context,
            "entities": self.entities,
            "policy_version": self.policy_version,
            "bundle_hash": self.bundle_hash,
        }


@dataclass(frozen=True, slots=True)
class CedarAuthorizationResponse:
    request_id: str
    decision: str
    determining_policy_ids: tuple[str, ...]
    errors: tuple[str, ...]
    policy_version: str
    bundle_hash: str
    evaluation_us: int


@dataclass(frozen=True, slots=True)
class CedarHealth:
    status: str
    engine: str
    cedar_version: str
    policy_version: str
    bundle_hash: str
    schema_hash: str
    validation: str

