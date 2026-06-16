from __future__ import annotations

from enum import StrEnum


class AdapterFailureCategory(StrEnum):
    AUTH = "auth"
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    UNAVAILABLE = "unavailable"
    LOCAL_RUNTIME = "local_runtime"


class AdapterError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        category: AdapterFailureCategory,
        retryable: bool = False,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.category = category
        self.retryable = retryable
        self.request_id = request_id


def require_http_url(value: object, *, provider: str, request_id: str) -> str:
    if not isinstance(value, str) or not value.startswith(("https://", "http://")):
        raise AdapterError(
            f"{provider} returned an invalid media URL for request {request_id}.",
            provider=provider,
            category=AdapterFailureCategory.MALFORMED_RESPONSE,
            request_id=request_id,
        )
    return value
