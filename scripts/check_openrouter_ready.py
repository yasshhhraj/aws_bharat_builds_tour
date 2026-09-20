#!/usr/bin/env python3
"""Validate OpenRouter configuration and key metadata without model inference."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.runtime.model_factory import DefaultManifestModelFactory
from apps.runtime.runtime_settings import RuntimeSettings
from packages.domain.errors import ManifestError


CURRENT_KEY_URL = "https://openrouter.ai/api/v1/key"


def main() -> int:
    try:
        settings = RuntimeSettings.from_env()
        if settings.model_provider != "openrouter":
            raise ValueError("MANIFEST_MODEL_PROVIDER must be openrouter for this check.")
        DefaultManifestModelFactory().validate(settings)
        key = os.environ["OPENROUTER_API_KEY"].strip()
        request = Request(
            CURRENT_KEY_URL,
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") if isinstance(payload, dict) else None
        safe = {
            "status": "ready",
            "http_status": 200,
            "model_provider": settings.model_provider,
            "requested_model_id": settings.model_id,
            "provider_route_kind": settings.provider_route_kind,
            "is_free_tier": data.get("is_free_tier") if isinstance(data, dict) else None,
            "limit_remaining": data.get("limit_remaining") if isinstance(data, dict) else None,
            "expires_at": data.get("expires_at") if isinstance(data, dict) else None,
        }
        print(json.dumps(safe, sort_keys=True))
        return 0
    except HTTPError as exc:
        print(
            json.dumps(
                {"status": "not_ready", "http_status": exc.code, "error": "OPENROUTER_KEY_REJECTED"}
            ),
            file=sys.stderr,
        )
    except URLError:
        print(
            json.dumps(
                {"status": "not_ready", "error": "OPENROUTER_UNAVAILABLE"}
            ),
            file=sys.stderr,
        )
    except (ManifestError, ValueError, KeyError, json.JSONDecodeError) as exc:
        code = getattr(exc, "code", "OPENROUTER_CONFIGURATION_ERROR")
        message = getattr(exc, "message", str(exc))
        print(
            json.dumps({"status": "not_ready", "error": code, "message": message}),
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
