"""Enumerations shared by the Manifest runtime and API."""

from enum import Enum


class StringEnum(str, Enum):
    """Enum whose values serialize naturally as strings."""


class AgentName(StringEnum):
    INVENTORY = "inventory"
    DISPATCH = "dispatch"
    CARRIER = "carrier"
    CUSTOMER_COMMUNICATIONS = "customer_communications"


class EffectClass(StringEnum):
    READ = "read"
    REVERSIBLE_WRITE = "reversible_write"
    FINANCIAL_COMMIT = "financial_commit"
    PHYSICAL_COMMIT = "physical_commit"
    EXTERNAL_DISCLOSURE = "external_disclosure"


class RunStatus(StringEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(StringEnum):
    RUN_STARTED = "run_started"
    AGENT_STARTED = "agent_started"
    TOOL_ATTEMPTED = "tool_attempted"
    GOVERNANCE_OBSERVED = "governance_observed"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    AGENT_COMPLETED = "agent_completed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
