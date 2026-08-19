"""DandeLiion API v2 transport and simulation lifecycle support."""

# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import tempfile
import time
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import ijson
import numpy as np
import requests

from .exceptions import (
    DandeliionAPIException,
    DandeliionInterfaceException,
    DandeliionTimeoutError,
    DandeliionTokenValidationError,
)
from .solution import Solution
from .token import TokenValidation

logger = logging.getLogger(__name__)

RUN_STATUSES = frozenset(
    {
        "queued",
        "running",
        "cancel_requested",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
    }
)
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "timed_out"})
BACKENDS = frozenset({"lambda", "fargate"})
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
BUNDLE_FORMAT = "dandeliion-client-solution"
BUNDLE_VERSION = 2
DEFAULT_LOG_LIMIT = 64 * 1024
DOWNLOAD_CHUNK_SIZE = 64 * 1024
MAX_SELECTED_FIELDS = 100


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    """Return *value* as a mapping or raise a structured API error."""
    if not isinstance(value, Mapping):
        raise DandeliionAPIException(f"The API returned invalid {label}: expected an object.")
    return value


def _require_string(value: Any, label: str, *, allow_empty: bool = True) -> str:
    """Return *value* as a validated string."""
    if not isinstance(value, str) or (not allow_empty and not value):
        raise DandeliionAPIException(f"The API returned invalid {label}: expected a string.")
    return value


def _require_optional_string(value: Any, label: str) -> str | None:
    """Return a string-or-null API field after validating its type."""
    if value is not None and not isinstance(value, str):
        raise DandeliionAPIException(f"The API returned invalid {label}: expected a string or null.")
    return value


def _normalise_collection_url(api_url: str) -> str:
    """Validate a user API URL and normalize it to the v2 run collection."""
    if not isinstance(api_url, str) or not api_url:
        raise DandeliionInterfaceException("api_url must be a non-empty absolute URL.")
    parsed = urlparse(api_url)
    if not parsed.scheme or not parsed.hostname:
        raise DandeliionInterfaceException("api_url must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DandeliionInterfaceException("api_url must not contain credentials, a query, or a fragment.")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise DandeliionInterfaceException("api_url contains an invalid port.") from exc

    hostname = parsed.hostname.lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and hostname in local_hosts):
        raise DandeliionInterfaceException("api_url must use HTTPS (HTTP is allowed only for localhost).")

    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        path = "/api/v2/runs"
    elif path == "/api/v2":
        path = "/api/v2/runs"
    elif path != "/api/v2/runs":
        if "/v1" in path:
            raise DandeliionInterfaceException("DandeLiion client 2.0 does not support API v1 URLs.")
        raise DandeliionInterfaceException("api_url must be the service root, /api/v2, or the /api/v2/runs collection.")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _origin(url: str) -> tuple[str, str, int | None]:
    """Return a normalized scheme, host, and effective port tuple."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise DandeliionAPIException("The API returned a URL with an invalid port.") from exc
    if port is None:
        port = 443 if scheme == "https" else 80 if scheme == "http" else None
    return scheme, (parsed.hostname or "").lower(), port


def _expected_urls(collection_url: str, run_id: str) -> dict[str, str]:
    """Build the trusted resource URLs for one run."""
    base = f"{collection_url}/{run_id}"
    return {
        "self": base,
        "result": f"{base}/result",
        "log": f"{base}/log",
        "cancel": f"{base}/cancel",
    }


def _validated_urls(value: Any, collection_url: str, run_id: str) -> dict[str, str]:
    """Validate server-provided run links against their trusted origin and paths."""
    payload = _require_mapping(value, "run URLs")
    expected = _expected_urls(collection_url, run_id)
    trusted_origin = _origin(collection_url)
    validated: dict[str, str] = {}
    service_root = f"{urlparse(collection_url).scheme}://{urlparse(collection_url).netloc}/"
    for name, expected_url in expected.items():
        link = _require_string(payload.get(name), f"run URL '{name}'", allow_empty=False)
        resolved = urljoin(service_root, link)
        parsed = urlparse(resolved)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise DandeliionAPIException(f"The API returned an unsafe {name} URL.")
        if _origin(resolved) != trusted_origin:
            raise DandeliionAPIException(f"The API returned a cross-origin {name} URL.")
        if urlparse(resolved).path.rstrip("/") != urlparse(expected_url).path.rstrip("/"):
            raise DandeliionAPIException(f"The API returned an unexpected {name} URL.")
        validated[name] = expected_url
    return validated


def _validate_artifacts(value: Any) -> dict[str, Any]:
    """Validate and copy artifact metadata from a run response."""
    payload = _require_mapping(value, "artifact metadata")
    available = payload.get("available")
    if not isinstance(available, bool):
        raise DandeliionAPIException("The API returned invalid artifact availability.")
    result_size = payload.get("result_size")
    if result_size is not None and (
        not isinstance(result_size, int) or isinstance(result_size, bool) or result_size < 0
    ):
        raise DandeliionAPIException("The API returned invalid result_size metadata.")
    solution_fields = payload.get("solution_fields")
    if not isinstance(solution_fields, list) or any(
        not isinstance(field, str) or not field for field in solution_fields
    ):
        raise DandeliionAPIException("The API returned invalid solution field metadata.")
    if len(set(solution_fields)) != len(solution_fields):
        raise DandeliionAPIException("The API returned duplicate solution field metadata.")
    return {
        "available": available,
        "result_size": result_size,
        "solution_fields": list(solution_fields),
        "expires_at": _require_optional_string(payload.get("expires_at"), "artifact expiry"),
        "purged_at": _require_optional_string(payload.get("purged_at"), "artifact purge timestamp"),
    }


def _validate_run(
    value: Any,
    *,
    collection_url: str | None,
    expected_id: str | None = None,
    require_urls: bool = True,
) -> dict[str, Any]:
    """Validate a flat API v2 run object and return trusted local metadata."""
    payload = _require_mapping(value, "run metadata")
    run_id = _require_string(payload.get("id"), "run id", allow_empty=False)
    try:
        run_id = str(uuid.UUID(run_id))
    except (ValueError, AttributeError) as exc:
        raise DandeliionAPIException("The API returned an invalid run UUID.") from exc
    if expected_id is not None and run_id != expected_id:
        raise DandeliionAPIException(f"The API returned run {run_id}, but run {expected_id} was requested.")
    status = _require_string(payload.get("status"), "run status", allow_empty=False)
    if status not in RUN_STATUSES:
        raise DandeliionAPIException(f"The API returned unsupported run status '{status}'.")
    backend = _require_string(payload.get("backend"), "run backend", allow_empty=False)
    if backend not in BACKENDS:
        raise DandeliionAPIException(f"The API returned unsupported backend '{backend}'.")

    portal_validation = payload.get("portal_validation")
    if portal_validation:
        try:
            TokenValidation.from_dict(portal_validation)
        except (KeyError, TypeError, ValueError) as exc:
            raise DandeliionAPIException("The API returned invalid token validation metadata.") from exc
    elif not isinstance(portal_validation, Mapping):
        raise DandeliionAPIException("The API returned invalid token validation metadata.")

    provider_may_continue = payload.get("provider_may_continue")
    if not isinstance(provider_may_continue, bool):
        raise DandeliionAPIException("The API returned invalid provider_may_continue metadata.")

    run = {
        "id": run_id,
        "status": status,
        "backend": backend,
        "created_at": _require_string(payload.get("created_at"), "created_at", allow_empty=False),
        "updated_at": _require_string(payload.get("updated_at"), "updated_at", allow_empty=False),
        "provider_started_at": _require_optional_string(payload.get("provider_started_at"), "provider_started_at"),
        "provider_finished_at": _require_optional_string(payload.get("provider_finished_at"), "provider_finished_at"),
        "terminal_at": _require_optional_string(payload.get("terminal_at"), "terminal_at"),
        "cancel_requested_at": _require_optional_string(payload.get("cancel_requested_at"), "cancel_requested_at"),
        "provider_may_continue": provider_may_continue,
        "error_code": _require_string(payload.get("error_code"), "error_code"),
        "error_message": _require_string(payload.get("error_message"), "error_message"),
        "portal_validation": dict(portal_validation),
        "artifacts": _validate_artifacts(payload.get("artifacts")),
    }
    if require_urls:
        if collection_url is None:
            raise DandeliionAPIException("Cannot validate run URLs without an API URL.")
        run["urls"] = _validated_urls(payload.get("urls"), collection_url, run_id)
    elif collection_url is not None:
        run["urls"] = _expected_urls(collection_url, run_id)
    return run


def _bundle_item(filepath: Path, prefix: str) -> Any:
    """Read one value from a restore bundle without loading the complete file."""
    try:
        with filepath.open("rb") as handle:
            return next(ijson.items(handle, prefix, use_float=True))
    except StopIteration:
        return None
    except (OSError, ijson.JSONError, UnicodeError, ValueError) as exc:
        raise DandeliionAPIException("The restore file is not valid JSON.") from exc


def _bundle_has_result(filepath: Path) -> bool:
    """Return whether a restore bundle contains a non-null result object."""
    try:
        with filepath.open("rb") as handle:
            for prefix, event, _value in ijson.parse(handle, use_float=True):
                if prefix == "result":
                    if event == "null":
                        return False
                    if event == "start_map":
                        return True
                    raise DandeliionAPIException("The restore bundle contains invalid result data.")
    except (OSError, ijson.JSONError, UnicodeError, ValueError) as exc:
        raise DandeliionAPIException("The restore file is not valid JSON.") from exc
    raise DandeliionAPIException("The restore bundle does not contain a result member.")


def _result_array(value: Any, label: str) -> np.ndarray:
    """Convert a JSON array to a validated numeric NumPy array."""
    if not isinstance(value, list):
        raise DandeliionAPIException(f"{label} must be a JSON array.")
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise DandeliionAPIException(f"{label} contains invalid array data.") from exc
    if array.ndim < 1 or not np.issubdtype(array.dtype, np.number):
        raise DandeliionAPIException(f"{label} must contain numeric array data.")
    return array


def _validate_streamed_bundle_result(filepath: Path, expected_fields: list[str]) -> None:
    """Incrementally validate a downloaded result and its ordered field names."""
    result_started = False
    result_finished = False
    solution_started = False
    solution_finished = False
    fields: list[str] = []
    field_set: set[str] = set()
    pending_field: str | None = None
    try:
        with filepath.open("rb") as handle:
            for prefix, event, value in ijson.parse(handle, use_float=True):
                if pending_field is not None:
                    if event != "start_array":
                        raise DandeliionAPIException(f"The full result field '{pending_field}' is not a JSON array.")
                    pending_field = None
                if prefix == "result" and event == "start_map":
                    if result_started:
                        raise DandeliionAPIException("The full result contains duplicate result objects.")
                    result_started = True
                elif prefix == "result" and event == "end_map":
                    result_finished = True
                elif prefix == "result.Solution" and event == "start_map":
                    if solution_started:
                        raise DandeliionAPIException("The full result contains duplicate Solution objects.")
                    solution_started = True
                elif prefix == "result.Solution" and event == "map_key":
                    if value in field_set:
                        raise DandeliionAPIException(f"The full result contains duplicate field '{value}'.")
                    field_set.add(value)
                    fields.append(value)
                    pending_field = value
                elif prefix == "result.Solution" and event == "end_map":
                    solution_finished = True
    except DandeliionAPIException:
        raise
    except (OSError, ijson.JSONError, UnicodeError, ValueError) as exc:
        raise DandeliionAPIException("The API returned invalid full-result JSON.") from exc
    if not result_started or not result_finished or not solution_started or not solution_finished:
        raise DandeliionAPIException("The API result does not contain a complete Solution object.")
    if fields != expected_fields:
        raise DandeliionAPIException("The full result fields do not match run metadata.")


class Simulator:
    """Submit simulations and retrieve their state and results through API v2.

    Constructing a simulator creates one reusable HTTP session. Pass both
    ``api_url`` and ``api_key`` for online use, or pass ``None`` for both when
    the instance is used only by an offline restored :class:`Solution`.
    """

    def __init__(
        self,
        api_url: str | None,
        api_key: str | None,
        *,
        request_timeout: tuple[float, float] = (3.05, 30.0),
        result_timeout: tuple[float, float] = (3.05, 300.0),
        poll_interval: float = 1.0,
        max_poll_interval: float = 10.0,
        max_attempts: int = 3,
        _session: requests.Session | None = None,
    ):
        """Initialize an API v2 simulator.

        Args:
            api_url: DandeLiion service root, ``/api/v2`` URL, or exact
                ``/api/v2/runs`` collection URL. HTTPS is required except for
                local development. Pass ``None`` together with ``api_key`` to
                create an offline simulator for restore operations.
            api_key: API token containing exactly 64 lowercase hexadecimal
                characters. Pass ``None`` together with ``api_url`` for
                offline restore operations.
            request_timeout: ``(connect, read)`` timeout in seconds for normal
                API requests.
            result_timeout: ``(connect, read)`` timeout in seconds for streamed
                result requests.
            poll_interval: Initial number of seconds between status polls.
            max_poll_interval: Maximum number of seconds between unchanged
                status polls.
            max_attempts: Total attempts for retryable requests, including the
                first attempt.
            _session: Internal test hook for supplying a requests-compatible
                session. Application code should leave this unset.

        Raises:
            DandeliionInterfaceException: If credentials, URLs, timeouts,
                polling intervals, or retry settings are invalid.

        """
        if (api_url is None) != (api_key is None):
            raise DandeliionInterfaceException("api_url and api_key must either both be provided or both be omitted.")
        self.api_url = _normalise_collection_url(api_url) if api_url is not None else None
        self.api_key = api_key
        self.request_timeout = self._validate_timeout(request_timeout, "request_timeout")
        self.result_timeout = self._validate_timeout(result_timeout, "result_timeout")
        if (
            not isinstance(poll_interval, (int, float))
            or isinstance(poll_interval, bool)
            or not math.isfinite(poll_interval)
            or not isinstance(max_poll_interval, (int, float))
            or isinstance(max_poll_interval, bool)
            or not math.isfinite(max_poll_interval)
            or poll_interval <= 0
            or max_poll_interval < poll_interval
        ):
            raise DandeliionInterfaceException("poll_interval must be positive and no greater than max_poll_interval.")
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
            raise DandeliionInterfaceException("max_attempts must be a positive integer.")
        self.poll_interval = float(poll_interval)
        self.max_poll_interval = float(max_poll_interval)
        self.max_attempts = max_attempts
        self._session = _session or requests.Session()

    @staticmethod
    def _validate_timeout(value: tuple[float, float], label: str) -> tuple[float, float]:
        """Validate and normalize a requests ``(connect, read)`` timeout."""
        if (
            not isinstance(value, tuple)
            or len(value) != 2
            or any(
                not isinstance(item, (int, float)) or isinstance(item, bool) or not math.isfinite(item) or item <= 0
                for item in value
            )
        ):
            raise DandeliionInterfaceException(f"{label} must be a (connect, read) tuple of positive numbers.")
        return float(value[0]), float(value[1])

    def __repr__(self) -> str:
        """Return a representation that never exposes the API key."""
        key = "<redacted>" if self.api_key is not None else "None"
        return (
            f"Simulator(api_url={self.api_url!r}, api_key={key}, "
            f"request_timeout={self.request_timeout!r}, result_timeout={self.result_timeout!r})"
        )

    @property
    def _online(self) -> bool:
        """Return whether this simulator has both an API URL and credential."""
        return self.api_url is not None and self.api_key is not None

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """Build authenticated request headers without mutating caller data."""
        if not self._online:
            raise DandeliionAPIException(
                "This solution is offline. Restore it with an explicit v2 api_url and api_key."
            )
        assert self.api_key is not None
        if not TOKEN_RE.fullmatch(self.api_key):
            raise DandeliionInterfaceException("api_key must contain exactly 64 lowercase hexadecimal characters.")
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _retry_after(response: requests.Response) -> float | None:
        """Parse and clamp a numeric ``Retry-After`` response header."""
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            delay = float(value)
        except ValueError:
            return None
        return min(max(delay, 0.0), 60.0) if math.isfinite(delay) else None

    @staticmethod
    def _error_payload(response: requests.Response) -> dict[str, Any]:
        """Normalize a structured or fallback API error response."""
        try:
            payload = response.json()
        except (TypeError, ValueError, requests.RequestException):
            payload = None
        if not isinstance(payload, Mapping):
            return {
                "code": "http_error",
                "message": response.reason or "The request failed.",
                "request_id": response.headers.get("X-Request-ID"),
                "authorization_request_id": None,
                "token": None,
            }
        error = payload.get("error")
        if isinstance(error, Mapping):
            code = error.get("code") if isinstance(error.get("code"), str) else "request_failed"
            message = (
                error.get("message")
                if isinstance(error.get("message"), str)
                else response.reason or "The request failed."
            )
            request_id = error.get("request_id")
            authorization_request_id = error.get("authorization_request_id")
        elif isinstance(error, str):
            code = "request_failed"
            message = error
            request_id = response.headers.get("X-Request-ID")
            authorization_request_id = None
        else:
            code = "request_failed"
            message = response.reason or "The request failed."
            request_id = response.headers.get("X-Request-ID")
            authorization_request_id = None
        return {
            "code": code,
            "message": message,
            "request_id": request_id if isinstance(request_id, str) else None,
            "authorization_request_id": (
                authorization_request_id if isinstance(authorization_request_id, str) else None
            ),
            "token": payload.get("token"),
        }

    def _exception_for_response(
        self,
        response: requests.Response,
        *,
        idempotency_key: str | None = None,
        parsed_error: dict[str, Any] | None = None,
    ) -> DandeliionAPIException:
        """Create the appropriate public exception for an error response."""
        error = parsed_error or self._error_payload(response)
        message = f"DandeLiion API request failed ({response.status_code}, {error['code']}): {error['message']}"
        kwargs = {
            "status_code": response.status_code,
            "code": error["code"],
            "request_id": error["request_id"],
            "authorization_request_id": error["authorization_request_id"],
            "retry_after": self._retry_after(response),
            "idempotency_key": idempotency_key,
        }
        token_payload = error.get("token")
        if response.status_code == 403 and isinstance(token_payload, Mapping):
            try:
                validation = TokenValidation.from_dict(token_payload)
            except (KeyError, TypeError, ValueError):
                pass
            else:
                if not validation.valid:
                    return DandeliionTokenValidationError(message, validation, **kwargs)
        return DandeliionAPIException(message, **kwargs)

    def _request(
        self,
        method: str,
        url: str,
        *,
        expected_status: Iterable[int],
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
        params: list[tuple[str, Any]] | None = None,
        stream: bool = False,
        result_request: bool = False,
        idempotency_key: str | None = None,
        submission: bool = False,
    ) -> requests.Response:
        """Execute one bounded, redirect-free request with retry handling."""
        expected = set(expected_status)
        last_transport_error: requests.RequestException | None = None
        for attempt in range(self.max_attempts):
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=self._headers(headers),
                    data=data,
                    params=params,
                    timeout=self.result_timeout if result_request else self.request_timeout,
                    allow_redirects=False,
                    stream=stream,
                )
            except requests.RequestException as exc:
                last_transport_error = exc
                if attempt + 1 < self.max_attempts:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise DandeliionAPIException(
                    "Could not communicate with the DandeLiion API.",
                    code="transport_error",
                    idempotency_key=idempotency_key,
                ) from exc

            if 300 <= response.status_code < 400:
                response.close()
                raise DandeliionAPIException(
                    "The DandeLiion API returned a redirect, which the client refuses to follow.",
                    status_code=response.status_code,
                    code="redirect_refused",
                    idempotency_key=idempotency_key,
                )
            if response.status_code in expected:
                if _origin(response.url) != _origin(url):
                    response.close()
                    raise DandeliionAPIException(
                        "The API response came from an unexpected origin.",
                        code="cross_origin_response",
                        idempotency_key=idempotency_key,
                    )
                return response

            error = self._error_payload(response)
            retryable = response.status_code in RETRYABLE_STATUSES
            if submission and response.status_code == 409 and error["code"] == "submission_in_progress":
                retryable = True
            if error["code"] == "authorization_unknown":
                retryable = False
            if retryable and attempt + 1 < self.max_attempts:
                delay = self._retry_after(response)
                response.close()
                time.sleep(delay if delay is not None else 0.5 * (2**attempt))
                continue
            response_error = self._exception_for_response(
                response,
                idempotency_key=idempotency_key,
                parsed_error=error,
            )
            response.close()
            raise response_error
        raise DandeliionAPIException(
            "Could not communicate with the DandeLiion API.",
            code="transport_error",
            idempotency_key=idempotency_key,
        ) from last_transport_error

    def submit(
        self,
        parameters: dict,
        is_blocking: bool = True,
        *,
        idempotency_key: str | None = None,
    ) -> Solution:
        """Submit a BPX simulation to API v2.

        The request body and idempotency key are serialized once and reused
        unchanged for every automatic retry. When ``is_blocking`` is true,
        this method waits until the run reaches any terminal state before
        returning.

        Args:
            parameters: Validated BPX-compatible simulation parameters as a
                strict JSON-compatible dictionary.
            is_blocking: Whether to wait for the run to become terminal.
                Defaults to ``True``.
            idempotency_key: Optional stable key for replaying the same logical
                submission. It must contain 8–128 supported ASCII characters.
                A UUID is generated when omitted.

        Returns:
            A solution linked to the accepted API run.

        Raises:
            DandeliionInterfaceException: If the parameters or idempotency key
                are invalid.
            DandeliionTokenValidationError: If the API rejects the token.
            DandeliionAPIException: If submission or response validation fails.

        """
        if not self._online:
            raise DandeliionAPIException("Cannot submit through an offline Simulator. Provide api_url and api_key.")
        if not isinstance(parameters, dict):
            raise DandeliionInterfaceException("parameters must be a dictionary.")
        key = str(uuid.uuid4()) if idempotency_key is None else idempotency_key
        if not isinstance(key, str) or not IDEMPOTENCY_RE.fullmatch(key):
            raise DandeliionInterfaceException(
                "idempotency_key must contain 8-128 ASCII letters, digits, dots, underscores, colons, or hyphens."
            )
        try:
            body = json.dumps(
                parameters,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise DandeliionInterfaceException("parameters must be strict JSON-compatible data.") from exc
        assert self.api_url is not None
        response = self._request(
            "POST",
            self.api_url,
            expected_status={202},
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": key,
            },
            data=body,
            idempotency_key=key,
            submission=True,
        )
        try:
            run = _validate_run(response.json(), collection_url=self.api_url)
            location = response.headers.get("Location")
            if location:
                expected_location = run["urls"]["self"]
                resolved = urljoin(f"{urlparse(self.api_url).scheme}://{urlparse(self.api_url).netloc}/", location)
                if _origin(resolved) != _origin(self.api_url) or urlparse(resolved).path.rstrip("/") != urlparse(
                    expected_location
                ).path.rstrip("/"):
                    raise DandeliionAPIException("The API returned an unexpected Location header.")
        except (TypeError, ValueError, requests.RequestException) as exc:
            raise DandeliionAPIException("The API returned invalid run JSON.") from exc
        finally:
            response.close()

        solution = Solution(
            sim=self,
            run=run,
            idempotency_key=key,
            time_column="Time [s]",
        )
        if is_blocking:
            solution.join()
        return solution

    def _refresh(self, solution: Solution) -> str:
        """Refresh one solution's run metadata and return its status."""
        if not self._online:
            raise DandeliionAPIException("This incomplete solution is offline. Restore it with api_url and api_key.")
        url = solution._run["urls"]["self"]
        response = self._request("GET", url, expected_status={200})
        try:
            run = _validate_run(
                response.json(),
                collection_url=self.api_url,
                expected_id=solution.run_id,
            )
        except (TypeError, ValueError, requests.RequestException) as exc:
            raise DandeliionAPIException("The API returned invalid run JSON.") from exc
        finally:
            response.close()
        solution._set_run(run)
        return run["status"]

    def _get_status(self, solution: Solution) -> str:
        """Return cached terminal status or refresh a non-terminal run."""
        if solution._run["status"] not in TERMINAL_STATUSES:
            return self._refresh(solution)
        return solution._run["status"]

    def _join(self, solution: Solution, timeout: float | None = None) -> None:
        """Poll a run with adaptive backoff until it becomes terminal."""
        if timeout is not None and (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or timeout < 0
        ):
            raise DandeliionInterfaceException("timeout must be non-negative or None.")
        if solution._run["status"] in TERMINAL_STATUSES:
            return
        if not self._online:
            raise DandeliionAPIException(
                "Cannot join an incomplete offline solution. Restore it with api_url and api_key."
            )
        deadline = time.monotonic() + timeout if timeout is not None else None
        delay = self.poll_interval
        previous = solution._run["status"]
        while solution._run["status"] not in TERMINAL_STATUSES:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DandeliionTimeoutError(
                        f"Run {solution.run_id} did not become terminal within {timeout} seconds.",
                        code="join_timeout",
                    )
                sleep_for = min(delay, remaining)
            else:
                sleep_for = delay
            time.sleep(sleep_for)
            current = self._refresh(solution)
            delay = self.poll_interval if current != previous else min(delay * 1.5, self.max_poll_interval)
            previous = current

    @staticmethod
    def _ensure_succeeded(solution: Solution) -> None:
        """Require a succeeded run whose result artifact is still available."""
        status = solution._run["status"]
        if status != "succeeded":
            message = solution._run.get("error_message") or "The simulation result is not available."
            raise DandeliionAPIException(
                message,
                code=solution._run.get("error_code") or "result_not_available",
            )
        if not solution._run["artifacts"]["available"]:
            raise DandeliionAPIException(
                "The simulation result is no longer available.",
                code="result_not_available",
            )

    def _fetch_fields(self, solution: Solution, fields: list[str]) -> dict[str, np.ndarray]:
        """Stream and parse only the requested result fields."""
        if not self._online:
            raise DandeliionAPIException("This solution has no local result and is not connected to API v2.")
        self._ensure_succeeded(solution)
        if not fields:
            return {}
        response = self._request(
            "GET",
            solution._run["urls"]["result"],
            expected_status={200},
            params=[("field", field) for field in fields],
            stream=True,
            result_request=True,
        )
        response.raw.decode_content = True
        found: dict[str, np.ndarray] = {}
        try:
            for key, value in ijson.kvitems(response.raw, "Solution", use_float=True):
                if key not in fields or key in found:
                    raise DandeliionAPIException("The API returned unexpected selected-result fields.")
                found[key] = _result_array(value, f"Result field '{key}'")
        except (ijson.JSONError, UnicodeError, ValueError, OSError, requests.RequestException) as exc:
            raise DandeliionAPIException("The API returned invalid selected-result JSON.") from exc
        finally:
            response.close()
        if set(found) != set(fields):
            missing = ", ".join(field for field in fields if field not in found)
            raise DandeliionAPIException(f"The API omitted selected result fields: {missing}.")
        return found

    def _get_log(self, solution: Solution) -> str:
        """Append incremental log pages and return all cached log text."""
        if not self._online:
            return solution._log
        while True:
            response = self._request(
                "GET",
                solution._run["urls"]["log"],
                expected_status={200},
                params=[
                    ("offset", solution._log_offset),
                    ("limit", DEFAULT_LOG_LIMIT),
                ],
            )
            try:
                payload = _require_mapping(response.json(), "log data")
            except (TypeError, ValueError, requests.RequestException) as exc:
                raise DandeliionAPIException("The API returned invalid log JSON.") from exc
            finally:
                response.close()
            offset = payload.get("offset")
            next_offset = payload.get("next_offset")
            eof = payload.get("eof")
            text = payload.get("text")
            if (
                not isinstance(offset, int)
                or isinstance(offset, bool)
                or offset < 0
                or not isinstance(next_offset, int)
                or isinstance(next_offset, bool)
                or next_offset < offset
                or not isinstance(eof, bool)
                or not isinstance(text, str)
            ):
                raise DandeliionAPIException("The API returned invalid log metadata.")
            if offset != solution._log_offset:
                raise DandeliionAPIException("The API returned an unexpected log offset.")
            previous_offset = solution._log_offset
            if next_offset == previous_offset and text:
                raise DandeliionAPIException("The API returned log text without advancing the offset.")
            solution._log += text
            solution._log_offset = next_offset
            if eof or next_offset == previous_offset:
                return solution._log

    def _cancel(self, solution: Solution) -> str:
        """Request cancellation and cache the validated resulting run state."""
        if not self._online:
            raise DandeliionAPIException("Cannot cancel an offline solution. Restore it with api_url and api_key.")
        response = self._request(
            "POST",
            solution._run["urls"]["cancel"],
            expected_status={202},
        )
        try:
            run = _validate_run(
                response.json(),
                collection_url=self.api_url,
                expected_id=solution.run_id,
            )
        except (TypeError, ValueError, requests.RequestException) as exc:
            raise DandeliionAPIException("The API returned invalid cancellation JSON.") from exc
        finally:
            response.close()
        if run["status"] not in {"cancel_requested", "cancelled"}:
            raise DandeliionAPIException("The API returned an invalid cancellation state.")
        solution._set_run(run)
        return run["status"]

    def _copy_bundle(self, source: Path, target: Path) -> None:
        """Atomically copy an existing offline bundle to another path."""
        if source.resolve() == target.resolve():
            return
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
            ) as destination:
                temporary = Path(destination.name)
                with source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, destination, DOWNLOAD_CHUNK_SIZE)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _dump(self, solution: Solution, filepath: str | Path) -> None:
        """Atomically write solution metadata and any available streamed result."""
        target = Path(filepath)
        if not target.parent.exists():
            raise DandeliionInterfaceException("The destination directory does not exist.")

        if not self._online and solution._bundle_path is not None and solution._local_result:
            self._copy_bundle(solution._bundle_path, target)
            return

        if self._online and solution._run["status"] not in TERMINAL_STATUSES:
            try:
                self._refresh(solution)
                self._get_log(solution)
            except DandeliionAPIException:
                logger.info("Writing cached run metadata because the API is temporarily unavailable.")
        elif self._online:
            try:
                self._get_log(solution)
            except DandeliionAPIException:
                logger.info("Writing the cached log because the latest log could not be retrieved.")

        sanitized_run = {key: value for key, value in solution._run.items() if key != "urls"}
        header = {
            "format": BUNDLE_FORMAT,
            "format_version": BUNDLE_VERSION,
            "run": sanitized_run,
            "client": {
                "idempotency_key": solution._idempotency_key,
                "log_offset": solution._log_offset,
            },
            "log": solution._log,
        }
        prefix = (
            json.dumps(
                header,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")[:-1]
            + b',"result":'
        )

        result_response: requests.Response | None = None
        is_full_result_response = False
        if solution._run["status"] == "succeeded":
            self._ensure_succeeded(solution)
            result_url = solution._run["urls"]["result"]
            try:
                result_response = self._request(
                    "GET",
                    result_url,
                    expected_status={200},
                    headers={"Accept-Encoding": "identity"},
                    stream=True,
                    result_request=True,
                )
                is_full_result_response = True
            except DandeliionAPIException as exc:
                fields = solution._run["artifacts"]["solution_fields"]
                if exc.status_code != 404 or not fields:
                    raise
                # Keep the direct file route as the preferred path. The
                # selected endpoint is a streaming fallback for deployments
                # whose front proxy cannot currently serve the full artifact.
                if len(fields) > MAX_SELECTED_FIELDS:
                    raise DandeliionAPIException(
                        "The full-result route returned 404 and the result has more than "
                        f"{MAX_SELECTED_FIELDS} fields, so it cannot be recovered through "
                        "one selected-result stream.",
                        status_code=exc.status_code,
                        code="full_result_unavailable",
                        request_id=exc.request_id,
                    ) from exc
                result_response = self._request(
                    "GET",
                    result_url,
                    expected_status={200},
                    headers={"Accept-Encoding": "identity"},
                    params=[("field", field) for field in fields],
                    stream=True,
                    result_request=True,
                )
            content_type = result_response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                result_response.close()
                raise DandeliionAPIException("The API returned an unexpected result content type.")

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
            ) as destination:
                temporary = Path(destination.name)
                destination.write(prefix)
                transferred = 0
                if result_response is None:
                    destination.write(b"null")
                else:
                    try:
                        for chunk in result_response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                            if chunk:
                                destination.write(chunk)
                                transferred += len(chunk)
                    except requests.RequestException as exc:
                        raise DandeliionAPIException(
                            "The result download was interrupted.",
                            code="transport_error",
                        ) from exc
                    if transferred == 0:
                        raise DandeliionAPIException("The API returned an empty result.")
                    content_length = result_response.headers.get("Content-Length")
                    if content_length is not None:
                        try:
                            expected_length = int(content_length)
                        except ValueError as exc:
                            raise DandeliionAPIException("The API returned an invalid Content-Length.") from exc
                        if transferred != expected_length:
                            raise DandeliionAPIException(
                                "The result download ended before Content-Length bytes were received."
                            )
                    result_size = solution._run["artifacts"]["result_size"]
                    if is_full_result_response and result_size is not None and transferred != result_size:
                        raise DandeliionAPIException("The result download size does not match run metadata.")
                destination.write(b"}")
                destination.flush()
                os.fsync(destination.fileno())
            if result_response is not None:
                _validate_streamed_bundle_result(
                    temporary,
                    solution._run["artifacts"]["solution_fields"],
                )
            os.replace(temporary, target)
            temporary = None
        finally:
            if result_response is not None:
                result_response.close()
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def restore(
        cls,
        filepath: str | Path,
        api_key: str | None = None,
        api_url: str | None = None,
    ) -> Solution:
        """Restore a v2 solution bundle, optionally reconnecting it to API v2.

        Completed bundles containing a result work offline. An incomplete
        bundle may be reconnected only when both ``api_url`` and ``api_key``
        are supplied explicitly; persisted data never selects the destination
        to which a credential is sent.

        Args:
            filepath: Path to a client 2.0 solution bundle.
            api_key: API token used to reconnect an incomplete bundle. Must be
                supplied together with ``api_url``.
            api_url: DandeLiion API v2 service or run-collection URL used to
                reconnect an incomplete bundle. Must be supplied together with
                ``api_key``.

        Returns:
            A lazily loaded solution backed by the local result or reconnected
            API run.

        Raises:
            DandeliionInterfaceException: If the path, bundle version, or
                reconnection arguments are invalid.
            DandeliionAPIException: If bundle metadata or result data is
                malformed, inconsistent, or cannot be reconnected.

        """
        path = Path(filepath)
        if not path.is_file():
            raise DandeliionInterfaceException(f"Restore file does not exist: {path}")
        bundle_format = _bundle_item(path, "format")
        bundle_version = _bundle_item(path, "format_version")
        if bundle_format != BUNDLE_FORMAT or bundle_version != BUNDLE_VERSION:
            raise DandeliionInterfaceException(
                "Unsupported v1 restore format. DandeLiion client 2.0 restores only v2 bundles."
            )
        run_payload = _bundle_item(path, "run")
        client_payload = _require_mapping(_bundle_item(path, "client"), "bundle client metadata")
        log = _bundle_item(path, "log")
        if not isinstance(log, str):
            raise DandeliionAPIException("The restore bundle contains an invalid log.")
        idempotency_key = client_payload.get("idempotency_key")
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str) or not IDEMPOTENCY_RE.fullmatch(idempotency_key)
        ):
            raise DandeliionAPIException("The restore bundle contains an invalid idempotency key.")
        log_offset = client_payload.get("log_offset")
        if not isinstance(log_offset, int) or isinstance(log_offset, bool) or log_offset < 0:
            raise DandeliionAPIException("The restore bundle contains an invalid log offset.")
        has_result = _bundle_has_result(path)

        if (api_url is None) != (api_key is None):
            raise DandeliionInterfaceException("Reconnecting a restore bundle requires both api_url and api_key.")
        sim = cls(api_url=api_url, api_key=api_key)
        run = _validate_run(
            run_payload,
            collection_url=sim.api_url,
            require_urls=False,
        )
        if has_result and run["status"] != "succeeded":
            raise DandeliionAPIException("The restore bundle contains a result for a run that did not succeed.")
        solution = Solution(
            sim=sim,
            run=run,
            idempotency_key=idempotency_key,
            log=log,
            log_offset=log_offset,
            bundle_path=path,
            local_result=has_result,
            time_column="Time [s]",
        )
        if sim._online and run["status"] not in TERMINAL_STATUSES:
            sim._refresh(solution)
        return solution
