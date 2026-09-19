"""Policy-engine interfaces, reference implementation, and startup factory."""

import os
from pathlib import Path

from .python_engine import PythonReferencePolicyEngine
from .protocol import PolicyEngine


def build_policy_engine_from_env() -> PolicyEngine:
    selected = os.environ.get("MANIFEST_POLICY_ENGINE", "python_reference").strip()
    if selected == "python_reference":
        engine: PolicyEngine = PythonReferencePolicyEngine()
    elif selected == "cedar":
        from packages.cedar_adapter import CedarClient, CedarPolicyEngine

        endpoint = os.environ.get("CEDAR_ENDPOINT", "http://127.0.0.1:8765")
        timeout_raw = os.environ.get("CEDAR_TIMEOUT_MS", "100")
        try:
            timeout_ms = int(timeout_raw)
        except ValueError as exc:
            raise ValueError("CEDAR_TIMEOUT_MS must be an integer.") from exc
        metadata_path = Path(
            os.environ.get(
                "CEDAR_POLICY_METADATA_PATH", "policies/demo-v1/metadata.json"
            )
        )
        expected_hash = os.environ.get("CEDAR_EXPECTED_BUNDLE_SHA256") or None
        engine = CedarPolicyEngine(
            CedarClient(endpoint, timeout_ms=timeout_ms),
            metadata_path=metadata_path,
            expected_bundle_hash=expected_hash,
        )
    else:
        raise ValueError(f"Unknown policy engine {selected!r}.")
    engine.validate_startup()
    return engine

__all__ = ["PolicyEngine", "PythonReferencePolicyEngine", "build_policy_engine_from_env"]
