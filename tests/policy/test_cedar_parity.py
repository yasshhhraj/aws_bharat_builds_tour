import json
import re
from pathlib import Path

from packages.governor.reasons import REASON_CODES
from packages.tools import build_tool_registry
from fixtures import FixtureLoader


def test_cedar_bundle_and_metadata_have_stable_complete_ids():
    source = Path("policies/demo-v1/manifest.cedar").read_text(encoding="utf-8")
    metadata = json.loads(
        Path("policies/demo-v1/metadata.json").read_text(encoding="utf-8")
    )["policies"]
    cedar_ids = set(re.findall(r'@id\("([A-Z0-9-]+)"\)', source))
    synthetic_allow_ids = {"SPEND-004", "SPEND-009"}
    assert cedar_ids == set(metadata) - synthetic_allow_ids
    assert all(item["reason_code"] in REASON_CODES for item in metadata.values())


def test_cedar_schema_declares_every_registered_action():
    schema = json.loads(
        Path("policies/schema/manifest.cedarschema.json").read_text(encoding="utf-8")
    )["Manifest"]
    registry, _ = build_tool_registry(FixtureLoader())
    registered = {item.name for item in registry.list_definitions()}
    assert set(schema["actions"]) == registered
