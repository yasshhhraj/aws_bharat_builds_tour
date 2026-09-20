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


class AgentRuntimeError(ManifestError):
    code = "AGENT_RUNTIME_ERROR"


class RuntimeConfigurationError(ManifestError):
    code = "RUNTIME_CONFIGURATION_ERROR"


class ProviderConfigurationError(RuntimeConfigurationError):
    code = "PROVIDER_CONFIGURATION_ERROR"


class ProviderError(AgentRuntimeError):
    code = "PROVIDER_ERROR"


class ProviderAuthenticationError(ProviderError):
    code = "PROVIDER_AUTHENTICATION_ERROR"


class ProviderBillingError(ProviderError):
    code = "PROVIDER_BILLING_ERROR"


class ProviderModelUnavailableError(ProviderError):
    code = "PROVIDER_MODEL_UNAVAILABLE"


class ProviderRateLimitError(ProviderError):
    code = "PROVIDER_RATE_LIMITED"


class ProviderTimeoutError(ProviderError):
    code = "PROVIDER_TIMEOUT"


class ProviderUnavailableError(ProviderError):
    code = "PROVIDER_UNAVAILABLE"


class AgentIncompleteError(AgentRuntimeError):
    code = "AGENT_INCOMPLETE"


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


class LedgerError(ManifestError):
    code = "LEDGER_ERROR"


class LedgerAppendError(LedgerError):
    code = "LEDGER_APPEND_ERROR"


class LedgerIdempotencyConflictError(LedgerError):
    code = "LEDGER_IDEMPOTENCY_CONFLICT"


class LedgerTamperDisabledError(LedgerError):
    code = "LEDGER_TAMPER_DISABLED"


class LedgerTamperUnauthorizedError(LedgerError):
    code = "LEDGER_TAMPER_UNAUTHORIZED"


class LedgerTamperValidationError(LedgerError):
    code = "LEDGER_TAMPER_VALIDATION_ERROR"


class StorageError(ManifestError):
    code = "STORAGE_ERROR"


class StorageConfigurationError(StorageError):
    code = "STORAGE_CONFIGURATION_ERROR"


class StorageUnavailableError(StorageError):
    code = "STORAGE_UNAVAILABLE"


class TraceRevisionConflictError(StorageError):
    code = "TRACE_REVISION_CONFLICT"


class TracePersistenceError(StorageError):
    code = "TRACE_PERSISTENCE_ERROR"


class ApprovalPersistenceConflictError(StorageError):
    code = "APPROVAL_PERSISTENCE_CONFLICT"


class EffectReceiptConflictError(StorageError):
    code = "EFFECT_RECEIPT_CONFLICT"


class SerializationVersionError(StorageError):
    code = "SERIALIZATION_VERSION_ERROR"


class ItemSizeLimitError(StorageError):
    code = "ITEM_SIZE_LIMIT_ERROR"
