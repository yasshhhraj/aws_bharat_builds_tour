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
    BLOCKED = "blocked"
    PENDING_APPROVAL = "pending_approval"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GovernanceMode(StringEnum):
    SHADOW = "shadow"
    ENFORCE = "enforce"


class ScenarioName(StringEnum):
    BENIGN = "benign"
    ADVERSARIAL = "adversarial"


class DecisionOutcome(StringEnum):
    ALLOW = "allow"
    GUIDE = "guide"
    BLOCK = "block"
    ESCALATE = "escalate"


class CommitmentStatus(StringEnum):
    PREPARED = "prepared"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ApprovalDecision(StringEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalStatus(StringEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class WorkflowStage(StringEnum):
    STARTED = "started"
    INVENTORY_COMPLETE = "inventory_complete"
    DISPATCH_COMPLETE = "dispatch_complete"
    BOOKING_PREPARED = "booking_prepared"
    AWAITING_APPROVAL = "awaiting_approval"
    BOOKING_CONFIRMED = "booking_confirmed"
    NOTIFICATION_SENT = "notification_sent"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    FAILED = "failed"


class EventType(StringEnum):
    RUN_STARTED = "run_started"
    AGENT_STARTED = "agent_started"
    TOOL_ATTEMPTED = "tool_attempted"
    GOVERNANCE_OBSERVED = "governance_observed"
    POLICY_DECIDED = "policy_decided"
    TOOL_GUIDED = "tool_guided"
    TOOL_BLOCKED = "tool_blocked"
    APPROVAL_REQUIRED = "approval_required"
    RUN_PAUSED = "run_paused"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    AGENT_COMPLETED = "agent_completed"
    AGENT_MODEL_COMPLETED = "agent_model_completed"
    AGENT_PAUSED = "agent_paused"
    AGENT_RESUMED = "agent_resumed"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    RUN_RESUMED = "run_resumed"
    RUN_CANCELLED = "run_cancelled"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
