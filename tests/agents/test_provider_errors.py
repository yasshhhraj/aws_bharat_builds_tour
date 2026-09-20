import pytest

from apps.runtime.provider_errors import classify_provider_error
from packages.domain.errors import (
    AgentRuntimeError,
    ProviderAuthenticationError,
    ProviderBillingError,
    ProviderModelUnavailableError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class ProviderFailure(Exception):
    def __init__(self, status_code=None):
        super().__init__("raw-provider-body-with-secret")
        self.status_code = status_code


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (401, ProviderAuthenticationError),
        (403, ProviderAuthenticationError),
        (402, ProviderBillingError),
        (404, ProviderModelUnavailableError),
        (429, ProviderRateLimitError),
        (500, ProviderUnavailableError),
    ),
)
def test_status_codes_map_to_stable_sanitized_errors(status, expected):
    error = classify_provider_error("openrouter", ProviderFailure(status))

    assert isinstance(error, expected)
    assert "raw-provider-body-with-secret" not in error.message


def test_timeout_class_name_is_classified_without_copying_message():
    class RequestTimeout(Exception):
        pass

    error = classify_provider_error("openrouter", RequestTimeout("sensitive"))

    assert isinstance(error, ProviderTimeoutError)
    assert "sensitive" not in error.message


def test_existing_manifest_error_is_preserved():
    original = AgentRuntimeError("safe project error")

    assert classify_provider_error("openrouter", original) is original
