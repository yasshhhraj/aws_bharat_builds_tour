"""Typed errors with safe messages suitable for CLI and API responses."""


class ManifestError(Exception):
    code = "MANIFEST_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class FixtureError(ManifestError):
    code = "FIXTURE_ERROR"


class OrderNotFoundError(ManifestError):
    code = "ORDER_NOT_FOUND"


class UnknownToolError(ManifestError):
    code = "UNKNOWN_TOOL"


class ToolOwnershipError(ManifestError):
    code = "TOOL_OWNERSHIP_ERROR"


class TraceNotFoundError(ManifestError):
    code = "TRACE_NOT_FOUND"


class TraceSequenceError(ManifestError):
    code = "TRACE_SEQUENCE_ERROR"


class NoSuitableVehicleError(ManifestError):
    code = "NO_SUITABLE_VEHICLE"


class NoSuitableCarrierError(ManifestError):
    code = "NO_SUITABLE_CARRIER"


class ToolExecutionError(ManifestError):
    code = "TOOL_EXECUTION_ERROR"


class UnsupportedModeError(ManifestError):
    code = "UNSUPPORTED_MODE"


class UnsupportedScenarioError(ManifestError):
    code = "UNSUPPORTED_SCENARIO"


class PolicyConfigurationError(ManifestError):
    code = "POLICY_CONFIGURATION_ERROR"


class IdempotencyConflictError(ManifestError):
    code = "IDEMPOTENCY_CONFLICT"


class PolicyBlockedError(ManifestError):
    code = "POLICY_BLOCKED"


class ApprovalNotFoundError(ManifestError):
    code = "APPROVAL_NOT_FOUND"


class ApprovalNotPendingError(ManifestError):
    code = "APPROVAL_NOT_PENDING"


class ApprovalVersionConflictError(ManifestError):
    code = "APPROVAL_VERSION_CONFLICT"


class ApprovalIdempotencyConflictError(ManifestError):
    code = "APPROVAL_IDEMPOTENCY_CONFLICT"


class ApprovalExpiredError(ManifestError):
    code = "APPROVAL_EXPIRED"


class ApprovalBindingError(ManifestError):
    code = "APPROVAL_BINDING_ERROR"


class ApprovalActionMismatchError(ApprovalBindingError):
    code = "APPROVAL_ACTION_MISMATCH"


class ApprovalStateMismatchError(ApprovalBindingError):
    code = "APPROVAL_STATE_MISMATCH"


class ApprovalPolicyMismatchError(ApprovalBindingError):
    code = "APPROVAL_POLICY_MISMATCH"


class ApproverConflictError(ManifestError):
    code = "APPROVER_CONFLICT"


class ApproverUnauthorizedError(ManifestError):
    code = "APPROVER_UNAUTHORIZED"


class ApprovalAuthNotConfiguredError(ManifestError):
    code = "APPROVAL_AUTH_NOT_CONFIGURED"
