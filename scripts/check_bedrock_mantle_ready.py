#!/usr/bin/env python3
"""Validate Bedrock Mantle configuration and model discovery without inference."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.runtime.model_factory import (
    DefaultManifestModelFactory,
    bedrock_mantle_base_url,
)
from apps.runtime.runtime_settings import RuntimeSettings
from packages.domain.errors import ManifestError


def main() -> int:
    try:
        settings = RuntimeSettings.from_env()
        if settings.model_provider != "bedrock_mantle":
            raise ValueError(
                "MANIFEST_MODEL_PROVIDER must be bedrock_mantle for this check."
            )
        DefaultManifestModelFactory().validate(settings)
        key = os.environ["BEDROCK_MANTLE_API_KEY"].strip()
        endpoint = bedrock_mantle_base_url(settings.bedrock_region)
        request = Request(
            f"{endpoint}/models",
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") if isinstance(payload, dict) else None
        model_ids = {
            item.get("id")
            for item in data or []
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        available = settings.model_id in model_ids
        safe = {
            "status": "ready" if available else "model_not_available",
            "http_status": 200,
            "model_provider": settings.model_provider,
            "requested_model_id": settings.model_id,
            "bedrock_region": settings.bedrock_region,
            "provider_route_kind": settings.provider_route_kind,
            "configured_model_available": available,
            "discovered_model_count": len(model_ids),
        }
        print(json.dumps(safe, sort_keys=True))
        return 0 if available else 1
    except HTTPError as exc:
        print(
            json.dumps(
                {
                    "status": "not_ready",
                    "http_status": exc.code,
                    "error": "BEDROCK_MANTLE_KEY_OR_PERMISSION_REJECTED",
                }
            ),
            file=sys.stderr,
        )
    except URLError:
        print(
            json.dumps(
                {"status": "not_ready", "error": "BEDROCK_MANTLE_UNAVAILABLE"}
            ),
            file=sys.stderr,
        )
    except (ManifestError, ValueError, KeyError, json.JSONDecodeError) as exc:
        code = getattr(exc, "code", "BEDROCK_MANTLE_CONFIGURATION_ERROR")
        message = getattr(exc, "message", str(exc))
        print(
            json.dumps({"status": "not_ready", "error": code, "message": message}),
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
