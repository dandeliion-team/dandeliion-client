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
        super().__init__(message, **kwargs)
        self.validation = validation


class DandeliionTimeoutError(DandeliionAPIException):
    """Raised when a caller-defined overall wait timeout expires."""
