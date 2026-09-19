"""Bounded loopback client for the Cedar PDP sidecar."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import CedarAuthorizationRequest, CedarAuthorizationResponse, CedarHealth


class CedarClientError(RuntimeError):
    """Safe adapter error that never includes raw request data."""


class CedarClient:
    def __init__(self, endpoint: str, *, timeout_ms: int = 100) -> None:
        endpoint = endpoint.rstrip("/")
        if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("Checkpoint 7 Cedar endpoint must use loopback HTTP.")
        if timeout_ms < 1 or timeout_ms > 10_000:
            raise ValueError("Cedar timeout must be between 1 and 10000 milliseconds.")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_ms / 1000

    def health(self) -> CedarHealth:
        data = self._request("GET", "/health/ready")
        try:
            return CedarHealth(
                status=str(data["status"]),
                engine=str(data["engine"]),
                cedar_version=str(data["cedar_version"]),
                policy_version=str(data["policy_version"]),
                bundle_hash=str(data["bundle_hash"]),
                schema_hash=str(data["schema_hash"]),
                validation=str(data["validation"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CedarClientError("Cedar health response is invalid.") from exc

    def authorize(
        self, request: CedarAuthorizationRequest
    ) -> CedarAuthorizationResponse:
        data = self._request("POST", "/v1/authorize", request.as_dict())
        try:
            evaluation_us = data["evaluation_us"]
            if isinstance(evaluation_us, bool) or not isinstance(evaluation_us, int):
                raise TypeError("evaluation_us")
            policy_ids = data["determining_policy_ids"]
            errors = data["errors"]
            if not isinstance(policy_ids, list) or not isinstance(errors, list):
                raise TypeError("lists")
            return CedarAuthorizationResponse(
                request_id=str(data["request_id"]),
                decision=str(data["decision"]),
                determining_policy_ids=tuple(str(item) for item in policy_ids),
                errors=tuple(str(item) for item in errors),
                policy_version=str(data["policy_version"]),
                bundle_hash=str(data["bundle_hash"]),
                evaluation_us=evaluation_us,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CedarClientError("Cedar authorization response is invalid.") from exc

    def _request(
        self, method: str, path: str, body: dict | None = None
    ) -> dict:
        encoded = None
        headers = {"Accept": "application/json"}
        if body is not None:
            encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            if len(encoded) > 65_536:
                raise CedarClientError("Cedar authorization request is too large.")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.endpoint}{path}", data=encoded, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(65_537)
                if len(raw) > 65_536:
                    raise CedarClientError("Cedar response is too large.")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise CedarClientError("Cedar response is invalid.")
                return value
        except CedarClientError:
            raise
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise CedarClientError("Cedar policy service request failed.") from exc

