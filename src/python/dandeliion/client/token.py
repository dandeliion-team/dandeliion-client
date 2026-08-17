"""Public token-validation metadata returned by the DandeLiion API."""

# SPDX-License-Identifier: BSD-3-Clause

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

TokenStatus = Literal[
    "valid",
    "invalid",
    "expired",
    "deactivated",
    "usage_exhausted",
    "user_inactive",
]

SUPPORTED_TOKEN_STATUSES = frozenset(
    {
        "valid",
        "invalid",
        "expired",
        "deactivated",
        "usage_exhausted",
        "user_inactive",
    }
)


@dataclass(frozen=True)
class TokenValidation:
    """A point-in-time token validation result from a simulation submission.

    Args:
        valid: Whether the token was accepted.
        status: Token status reported by the Token Portal.
        expires_at: Timezone-aware token expiry, when provided.
        uses_remaining: Shared post-submission use balance, when provided.
        error: Token validation error text, when validation failed.

    """

    valid: bool
    status: TokenStatus
    expires_at: datetime | None
    uses_remaining: int | None
    error: str | None

    @classmethod
    def from_dict(cls, payload):
        """Build typed validation metadata from an API response object.

        Args:
            payload: Mapping containing ``valid``, ``status``, ``expires_at``,
                ``uses_remaining``, and ``error`` values.

        Returns:
            Validated token metadata.

        Raises:
            KeyError: If a required field is absent.
            TypeError: If a field has an invalid type.
            ValueError: If status, consistency, expiry, or balance validation
                fails.

        """
        if not isinstance(payload, dict):
            raise TypeError("Token validation metadata must be an object")

        valid = payload["valid"]
        status = payload["status"]
        expires_at = payload["expires_at"]
        uses_remaining = payload["uses_remaining"]
        error = payload["error"]

        if not isinstance(valid, bool):
            raise TypeError("Token validation 'valid' must be a boolean")
        if not isinstance(status, str) or status not in SUPPORTED_TOKEN_STATUSES:
            raise ValueError("Token validation status is not supported")
        if valid != (status == "valid"):
            raise ValueError("Token validation status is inconsistent")

        parsed_expiry = None
        if expires_at is not None:
            if not isinstance(expires_at, str):
                raise TypeError("Token expiry must be an ISO 8601 string")
            parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if parsed_expiry.tzinfo is None:
                raise ValueError("Token expiry must include a timezone")

        if uses_remaining is not None and (
            not isinstance(uses_remaining, int) or isinstance(uses_remaining, bool) or uses_remaining < 0
        ):
            raise ValueError("Token uses remaining must be a non-negative integer")
        if error is not None and not isinstance(error, str):
            raise TypeError("Token validation error must be a string or None")

        return cls(
            valid=valid,
            status=cast(TokenStatus, status),
            expires_at=parsed_expiry,
            uses_remaining=uses_remaining,
            error=error,
        )
