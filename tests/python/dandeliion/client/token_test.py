# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from datetime import timezone

import pytest
from dandeliion.client.token import TokenValidation


def valid_payload():
    """Return valid Token Portal metadata for mutation by individual tests."""
    return {
        "valid": True,
        "status": "valid",
        "expires_at": "2027-01-01T00:00:00Z",
        "uses_remaining": 4,
        "error": None,
    }


def test_parses_valid_metadata():
    """Parse valid token metadata into typed, timezone-aware values."""
    validation = TokenValidation.from_dict(valid_payload())
    assert validation.valid is True
    assert validation.expires_at.tzinfo == timezone.utc
    assert validation.uses_remaining == 4


@pytest.mark.parametrize(
    ("key", "value", "exception"),
    [
        ("valid", "yes", TypeError),
        ("status", "unknown", ValueError),
        ("status", "expired", ValueError),
        ("expires_at", 1, TypeError),
        ("expires_at", "not-a-date", ValueError),
        ("expires_at", "2027-01-01T00:00:00", ValueError),
        ("uses_remaining", True, ValueError),
        ("uses_remaining", -1, ValueError),
        ("error", 1, TypeError),
    ],
)
def test_rejects_invalid_metadata(key, value, exception):
    """Reject each invalid token field with the appropriate exception type."""
    payload = valid_payload()
    payload[key] = value
    with pytest.raises(exception):
        TokenValidation.from_dict(payload)


def test_rejects_non_mapping_and_missing_fields():
    """Reject non-object token metadata and objects missing required fields."""
    with pytest.raises(TypeError):
        TokenValidation.from_dict([])
    payload = valid_payload()
    del payload["status"]
    with pytest.raises(KeyError):
        TokenValidation.from_dict(payload)
