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
