"""Map provider/transport failures to stable secret-safe Manifest errors."""

from __future__ import annotations

from packages.domain.errors import (
    ManifestError,
    ProviderAuthenticationError,
    ProviderBillingError,
    ProviderModelUnavailableError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def classify_provider_error(provider: str, exc: Exception) -> ManifestError:
    """Return a safe error without copying provider response text."""

    if isinstance(exc, ManifestError):
        return exc
    status = _status_code(exc)
    class_name = type(exc).__name__.lower()
    label = {
        "openrouter": "OpenRouter",
        "bedrock_mantle": "Bedrock Mantle",
        "bedrock": "Bedrock",
    }.get(provider, provider.replace("_", " ").title())
    if status in {401, 403} or "authentication" in class_name or "permission" in class_name:
        return ProviderAuthenticationError(
            f"{label} rejected the configured authentication."
        )
    if status == 402:
        return ProviderBillingError(
            f"{label} rejected the selected model because billing or credits are required."
        )
    if status == 404 or "notfound" in class_name:
        return ProviderModelUnavailableError(
            f"{label} could not provide the selected model."
        )
    if status == 429 or "throttl" in class_name or "ratelimit" in class_name:
        return ProviderRateLimitError(
            f"{label} rate-limited the model request."
        )
    if "timeout" in class_name:
        return ProviderTimeoutError(f"{label} model request timed out.")
    return ProviderUnavailableError(
        f"{label} model request failed before the role could complete."
    )


def _status_code(exc: Exception) -> int | None:
    direct = getattr(exc, "status_code", None)
    if isinstance(direct, int):
        return direct
    response = getattr(exc, "response", None)
    nested = getattr(response, "status_code", None)
    return nested if isinstance(nested, int) else None
