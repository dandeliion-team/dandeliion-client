"""Public exceptions raised by the DandeLiion client."""

# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations


class DandeliionInterfaceException(Exception):
    """Raised when local client configuration or input is invalid."""


class DandeliionAPIException(Exception):
    """Raised when a DandeLiion API request cannot be completed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        authorization_request_id: str | None = None,
        retry_after: float | None = None,
        idempotency_key: str | None = None,
    ):
        """Initialize a structured API exception.

        Args:
            message: Human-readable error description.
            status_code: HTTP response status, when a response was received.
            code: Stable API or client error code.
            request_id: API request identifier for diagnostics.
            authorization_request_id: Token Portal reconciliation identifier.
            retry_after: Server-suggested retry delay in seconds.
            idempotency_key: Submission key associated with the failed request.

        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.authorization_request_id = authorization_request_id
        self.retry_after = retry_after
        self.idempotency_key = idempotency_key


class DandeliionTokenValidationError(DandeliionAPIException):
    """Raised when the API rejects a simulation submission's token."""

    def __init__(self, message: str, validation, **kwargs):
        """Initialize an API error with rejected-token metadata.

        Args:
            message: Human-readable error description.
            validation: Structured :class:`TokenValidation` rejection details.
            **kwargs: Structured fields accepted by
                :class:`DandeliionAPIException`.

        """
        super().__init__(message, **kwargs)
        self.validation = validation


class DandeliionTimeoutError(DandeliionAPIException):
    """Raised when a caller-defined overall wait timeout expires."""
