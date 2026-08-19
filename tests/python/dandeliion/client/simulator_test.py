# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import io
import json
from copy import deepcopy
from urllib.parse import urlencode

import numpy as np
import pytest
import requests
from dandeliion.client import (
    DandeliionAPIException,
    DandeliionInterfaceException,
    DandeliionTimeoutError,
    DandeliionTokenValidationError,
    Simulator,
)
from dandeliion.client.simulator import _bundle_has_result, _validate_run
from dandeliion.client.solution import Solution

API_ROOT = "https://api.example"
RUNS_URL = f"{API_ROOT}/api/v2/runs"
RUN_ID = "7ad965d1-7c66-47eb-b095-25a2c4c52f0f"
TOKEN = "a" * 64


class FakeResponse:
    """Provide the subset of a requests response needed by transport tests."""

    def __init__(
        self,
        *,
        status_code=200,
        json_data=None,
        body=None,
        headers=None,
        reason="",
        url=None,
        chunks=None,
    ):
        self.status_code = status_code
        self._json_data = json_data
        if body is None and json_data is not None:
            body = json.dumps(json_data, separators=(",", ":")).encode()
        self.body = body or b""
        self.headers = dict(headers or {})
        self.reason = reason
        self.url = url
        self.raw = io.BytesIO(self.body)
        self.raw.decode_content = False
        self._chunks = chunks
        self.closed = False

    def json(self):
        if self._json_data is not None:
            return self._json_data
        return json.loads(self.body)

    def iter_content(self, chunk_size):
        chunks = self._chunks
        if chunks is None:
            chunks = [self.body[index : index + chunk_size] for index in range(0, len(self.body), chunk_size)]
        for chunk in chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def close(self):
        self.closed = True


class FakeSession:
    """Record requests and return a deterministic sequence of HTTP events."""

    def __init__(self, *events):
        self.events = list(events)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.events:
            raise AssertionError("Unexpected HTTP request")
        event = self.events.pop(0)
        if isinstance(event, Exception):
            raise event
        if event.url is None:
            event.url = url
            if kwargs.get("params"):
                event.url = f"{url}?{urlencode(kwargs['params'])}"
        return event


def token_validation(valid=True, status="valid"):
    """Return internally consistent Token Portal validation metadata."""
    return {
        "valid": valid,
        "status": status,
        "expires_at": "2027-01-01T00:00:00Z" if status != "invalid" else None,
        "uses_remaining": 8 if valid else 0,
        "error": None if valid else status,
    }


def run_payload(
    status="queued",
    *,
    fields=None,
    available=None,
    result_size=None,
    urls=None,
):
    """Build a complete flat API v2 run payload for the requested state."""
    if fields is None:
        fields = [] if status != "succeeded" else ["Time [s]", "Voltage [V]"]
    if available is None:
        available = status == "succeeded"
    base = f"{RUNS_URL}/{RUN_ID}"
    return {
        "id": RUN_ID,
        "status": status,
        "backend": "lambda",
        "created_at": "2026-07-25T10:00:00Z",
        "updated_at": "2026-07-25T10:00:01Z",
        "provider_started_at": None,
        "provider_finished_at": None,
        "terminal_at": None
        if status not in {"succeeded", "failed", "cancelled", "timed_out"}
        else "2026-07-25T10:01:00Z",
        "cancel_requested_at": None,
        "provider_may_continue": False,
        "error_code": "",
        "error_message": "",
        "portal_validation": token_validation(),
        "artifacts": {
            "available": available,
            "result_size": result_size,
            "solution_fields": fields,
            "expires_at": None,
            "purged_at": None,
        },
        "urls": urls
        or {
            "self": base,
            "result": f"{base}/result",
            "log": f"{base}/log",
            "cancel": f"{base}/cancel",
        },
    }


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        (API_ROOT, RUNS_URL),
        (f"{API_ROOT}/", RUNS_URL),
        (f"{API_ROOT}/api/v2", RUNS_URL),
        (RUNS_URL, RUNS_URL),
    ],
)
def test_normalises_supported_api_urls(provided, expected):
    """Normalize every supported API URL form and redact the bearer token."""
    simulator = Simulator(provided, TOKEN)
    assert simulator.api_url == expected
    assert TOKEN not in repr(simulator)
    assert "<redacted>" in repr(simulator)


@pytest.mark.parametrize(
    "url",
    [
        f"{API_ROOT}/v1",
        "http://api.example",
        "https://user:pass@api.example",
        "https://api.example/api/v2/runs?x=1",
        "https://api.example:invalid",
        "not-a-url",
    ],
)
def test_rejects_unsafe_or_v1_api_urls(url):
    """Reject legacy, insecure, credential-bearing, and malformed API URLs."""
    with pytest.raises(DandeliionInterfaceException):
        Simulator(url, TOKEN)


def test_accepts_local_http_and_validates_configuration():
    """Allow local HTTP while rejecting invalid transport configuration."""
    assert Simulator("http://127.0.0.1:8000", TOKEN).api_url.endswith("/api/v2/runs")
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, None)
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, max_attempts=0)
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, request_timeout=(0, 1))
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, request_timeout=(True, 1))
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, poll_interval=float("nan"))


def test_submit_uses_flat_v2_contract_and_supplied_idempotency_key():
    """Send the exact v2 submission route, headers, body, and caller key."""
    response = FakeResponse(
        status_code=202,
        json_data=run_payload(),
        headers={"Location": f"{RUNS_URL}/{RUN_ID}"},
    )
    session = FakeSession(response)
    simulator = Simulator(API_ROOT, TOKEN, _session=session)
    parameters = {"Header": {"Description": "test"}}

    solution = simulator.submit(
        parameters,
        is_blocking=False,
        idempotency_key="simulation-0001",
    )

    assert solution.run_id == RUN_ID
    assert solution.idempotency_key == "simulation-0001"
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", RUNS_URL)
    assert kwargs["headers"]["Authorization"] == f"Token {TOKEN}"
    assert kwargs["headers"]["Idempotency-Key"] == "simulation-0001"
    assert kwargs["allow_redirects"] is False
    assert json.loads(kwargs["data"]) == parameters


def test_submit_generates_uuid_and_rejects_bad_input():
    """Generate a submission key and reject unsafe bodies or caller keys."""
    session = FakeSession(FakeResponse(status_code=202, json_data=run_payload()))
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit(
        {"Header": {}},
        is_blocking=False,
    )
    assert len(solution.idempotency_key) == 36

    # Strict serialization rejects non-finite JSON values before any request.
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, _session=FakeSession()).submit(
            {"value": float("nan")},
            is_blocking=False,
        )

    # Caller-supplied keys must satisfy the API's length and syntax contract.
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, _session=FakeSession()).submit(
            {},
            is_blocking=False,
            idempotency_key="short",
        )
    with pytest.raises(DandeliionInterfaceException):
        Simulator(API_ROOT, TOKEN, _session=FakeSession()).submit(
            {},
            is_blocking=False,
            idempotency_key="",
        )


def test_submission_retries_transport_failure_with_identical_body_and_key(monkeypatch):
    """Reuse identical serialized bytes and key after a transport failure."""
    session = FakeSession(
        requests.ConnectionError("lost"),
        FakeResponse(status_code=202, json_data=run_payload()),
    )
    sleeps = []
    monkeypatch.setattr("dandeliion.client.simulator.time.sleep", sleeps.append)
    simulator = Simulator(API_ROOT, TOKEN, _session=session)

    simulator.submit({}, is_blocking=False, idempotency_key="retry-key-0001")

    assert len(session.calls) == 2
    assert session.calls[0][2]["data"] == session.calls[1][2]["data"]
    assert session.calls[0][2]["headers"]["Idempotency-Key"] == "retry-key-0001"
    assert session.calls[1][2]["headers"]["Idempotency-Key"] == "retry-key-0001"
    assert sleeps == [0.5]


def test_retry_after_and_submission_in_progress_are_retried(monkeypatch):
    """Retry a transient idempotent reservation still in progress."""
    in_progress = FakeResponse(
        status_code=409,
        json_data={
            "error": {
                "code": "submission_in_progress",
                "message": "retry",
                "request_id": "r1",
            }
        },
    )
    accepted = FakeResponse(status_code=202, json_data=run_payload())
    session = FakeSession(in_progress, accepted)
    monkeypatch.setattr("dandeliion.client.simulator.time.sleep", lambda _delay: None)
    Simulator(API_ROOT, TOKEN, _session=session).submit(
        {},
        is_blocking=False,
        idempotency_key="retry-key-0002",
    )
    assert len(session.calls) == 2


def test_authorization_unknown_is_not_retried():
    """Surface authorization reconciliation identifiers without retrying."""
    response = FakeResponse(
        status_code=503,
        json_data={
            "error": {
                "code": "authorization_unknown",
                "message": "contact support",
                "request_id": "request-2",
                "authorization_request_id": "portal-1",
            }
        },
    )
    session = FakeSession(response)
    with pytest.raises(DandeliionAPIException) as raised:
        Simulator(API_ROOT, TOKEN, _session=session).submit(
            {},
            is_blocking=False,
            idempotency_key="unknown-key-01",
        )
    assert len(session.calls) == 1
    assert raised.value.code == "authorization_unknown"
    assert raised.value.request_id == "request-2"
    assert raised.value.authorization_request_id == "portal-1"
    assert raised.value.idempotency_key == "unknown-key-01"


def test_structured_token_rejection():
    """Expose rejected Token Portal metadata on the typed public exception."""
    response = FakeResponse(
        status_code=403,
        json_data={
            "error": {
                "code": "token_usage_exhausted",
                "message": "usage exhausted",
                "request_id": "request-3",
            },
            "token": token_validation(False, "usage_exhausted"),
        },
    )
    with pytest.raises(DandeliionTokenValidationError) as raised:
        Simulator(API_ROOT, TOKEN, _session=FakeSession(response)).submit(
            {},
            is_blocking=False,
            idempotency_key="token-key-0001",
        )
    assert raised.value.validation.status == "usage_exhausted"
    assert raised.value.validation.uses_remaining == 0


def test_cross_origin_and_malformed_run_responses_are_rejected():
    """Reject untrusted result links and malformed flat run metadata."""
    payload = run_payload()
    payload["urls"]["result"] = "https://attacker.example/result"
    with pytest.raises(DandeliionAPIException, match="cross-origin"):
        Simulator(
            API_ROOT,
            TOKEN,
            _session=FakeSession(FakeResponse(status_code=202, json_data=payload)),
        ).submit({}, is_blocking=False)

    # Even same-origin responses must satisfy the complete run schema.
    malformed = run_payload()
    malformed["artifacts"]["available"] = 0
    with pytest.raises(DandeliionAPIException, match="availability"):
        Simulator(
            API_ROOT,
            TOKEN,
            _session=FakeSession(FakeResponse(status_code=202, json_data=malformed)),
        ).submit({}, is_blocking=False)


def test_status_polling_and_join_backoff(monkeypatch):
    """Back off unchanged status polls and reset after each state transition."""
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("queued")),
        FakeResponse(status_code=200, json_data=run_payload("queued")),
        FakeResponse(status_code=200, json_data=run_payload("running")),
        FakeResponse(status_code=200, json_data=run_payload("succeeded")),
    )
    simulator = Simulator(API_ROOT, TOKEN, _session=session)
    solution = simulator.submit({}, is_blocking=False)
    sleeps = []
    monkeypatch.setattr("dandeliion.client.simulator.time.sleep", sleeps.append)

    solution.join()

    assert solution.status == "succeeded"
    assert sleeps == [1.0, 1.5, 1.0]


def test_join_timeout_and_offline_join(monkeypatch):
    """Raise the typed timeout once a caller's overall join limit expires."""
    session = FakeSession(FakeResponse(status_code=202, json_data=run_payload("queued")))
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    times = iter([0.0, 2.0])
    monkeypatch.setattr("dandeliion.client.simulator.time.monotonic", lambda: next(times))
    with pytest.raises(DandeliionTimeoutError):
        solution.join(timeout=1)


def test_incremental_logs_are_appended_without_duplicates():
    """Follow log offsets across pages without appending content twice."""
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("running")),
        FakeResponse(
            status_code=200,
            json_data={"offset": 0, "next_offset": 3, "eof": False, "text": "abc"},
        ),
        FakeResponse(
            status_code=200,
            json_data={"offset": 3, "next_offset": 5, "eof": True, "text": "de"},
        ),
        FakeResponse(
            status_code=200,
            json_data={"offset": 5, "next_offset": 5, "eof": True, "text": ""},
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    assert solution.log == "abcde"
    assert solution.log == "abcde"
    assert session.calls[1][2]["params"] == [("offset", 0), ("limit", 65536)]
    assert session.calls[3][2]["params"] == [("offset", 5), ("limit", 65536)]


def test_selected_results_use_repeated_fields_and_streamed_json():
    """Stream ordered repeated-field results, interpolate, and cache them."""
    selected = b'{"Solution":{"Time [s]":[0,1],"Voltage [V]":[4.2,4.1]}}'
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("succeeded")),
        FakeResponse(
            status_code=200,
            body=selected,
            headers={"Content-Type": "application/json"},
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)

    voltage = solution["Voltage [V]"]

    np.testing.assert_allclose(voltage, [4.2, 4.1])
    assert voltage(t=0.5) == pytest.approx(4.15)
    assert session.calls[1][2]["params"] == [
        ("field", "Time [s]"),
        ("field", "Voltage [V]"),
    ]
    assert solution["Voltage [V]"] is not voltage
    assert len(session.calls) == 2


def test_cancellation_updates_run():
    """Post to the cancel route and cache the returned terminal run state."""
    cancelled = run_payload("cancelled")
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("running")),
        FakeResponse(status_code=202, json_data=cancelled),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    assert solution.cancel() == "cancelled"
    assert solution.status == "cancelled"
    assert session.calls[1][0:2] == ("POST", f"{RUNS_URL}/{RUN_ID}/cancel")


def test_cancellation_rejects_invalid_state_and_propagates_terminal_error():
    """Reject malformed cancellation success and preserve terminal API errors."""
    # A nominally successful response must contain a cancellation state.
    invalid_session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("running")),
        FakeResponse(status_code=202, json_data=run_payload("running")),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=invalid_session).submit(
        {},
        is_blocking=False,
    )
    with pytest.raises(DandeliionAPIException, match="invalid cancellation state"):
        solution.cancel()

    # A completed run preserves the API's structured run_not_cancellable error.
    error_session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("succeeded")),
        FakeResponse(
            status_code=409,
            json_data={
                "error": {
                    "code": "run_not_cancellable",
                    "message": "The run has already finished.",
                    "request_id": "request-cancel-1",
                }
            },
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=error_session).submit(
        {},
        is_blocking=False,
    )
    with pytest.raises(DandeliionAPIException) as raised:
        solution.cancel()
    assert raised.value.code == "run_not_cancellable"
    assert raised.value.request_id == "request-cancel-1"


def test_dump_streams_atomic_v2_bundle_and_restores_offline(tmp_path):
    """Stream a sanitized v2 bundle that restores complete results offline."""
    result = b'{"Solution":{"Time [s]":[0,1],"Voltage [V]":[4.2,4.1]}}'
    run = run_payload("succeeded", result_size=len(result))
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run),
        FakeResponse(
            status_code=200,
            json_data={"offset": 0, "next_offset": 4, "eof": True, "text": "done"},
        ),
        FakeResponse(
            status_code=200,
            body=result,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(result)),
            },
            chunks=[result[:10], result[10:]],
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit(
        {},
        is_blocking=False,
        idempotency_key="bundle-key-0001",
    )
    target = tmp_path / "solution.json"

    solution.dump(target)

    payload = json.loads(target.read_text())
    assert payload["format"] == "dandeliion-client-solution"
    assert payload["format_version"] == 2
    assert "urls" not in payload["run"]
    assert payload["client"]["idempotency_key"] == "bundle-key-0001"
    assert payload["log"] == "done"
    assert payload["result"]["Solution"]["Voltage [V]"] == [4.2, 4.1]
    restored = Simulator.restore(target)
    assert restored.status == "succeeded"
    assert restored.log == "done"
    np.testing.assert_allclose(restored["Voltage [V]"], [4.2, 4.1])
    assert TOKEN not in target.read_text()


def test_dump_falls_back_to_selected_stream_when_full_route_returns_404(tmp_path):
    """Reconstruct a full bundle from selected fields when direct download is absent."""
    selected = b'{"Solution":{"Time [s]":[0,1],"Voltage [V]":[4.2,4.1]}}'
    run = run_payload("succeeded", result_size=len(selected) + 100)
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run),
        FakeResponse(
            status_code=200,
            json_data={"offset": 0, "next_offset": 0, "eof": True, "text": ""},
        ),
        FakeResponse(status_code=404, json_data={"error": "not_found"}),
        FakeResponse(
            status_code=200,
            body=selected,
            headers={"Content-Type": "application/json"},
            chunks=[selected[:11], selected[11:]],
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    target = tmp_path / "solution.json"

    solution.dump(target)

    assert session.calls[2][2]["params"] is None
    assert session.calls[3][2]["params"] == [
        ("field", "Time [s]"),
        ("field", "Voltage [V]"),
    ]
    assert session.calls[3][2]["headers"]["Accept-Encoding"] == "identity"
    restored = Simulator.restore(target)
    np.testing.assert_allclose(restored["Voltage [V]"], [4.2, 4.1])


def test_dump_reports_when_full_route_fallback_exceeds_field_limit(tmp_path):
    """Report when the fallback cannot request all fields in one selection."""
    fields = [f"Field {index}" for index in range(101)]
    session = FakeSession(
        FakeResponse(
            status_code=202,
            json_data=run_payload("succeeded", fields=fields),
        ),
        FakeResponse(
            status_code=200,
            json_data={"offset": 0, "next_offset": 0, "eof": True, "text": ""},
        ),
        FakeResponse(status_code=404, json_data={"error": "not_found"}),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)

    with pytest.raises(DandeliionAPIException) as raised:
        solution.dump(tmp_path / "solution.json")
    assert raised.value.code == "full_result_unavailable"
    assert raised.value.status_code == 404


def test_incomplete_bundle_requires_explicit_pair_to_reconnect(tmp_path):
    """Persist unreachable runs offline and require explicit reconnection credentials."""
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("queued")),
        requests.ConnectionError("offline"),
        requests.ConnectionError("offline"),
        requests.ConnectionError("offline"),
    )
    simulator = Simulator(API_ROOT, TOKEN, _session=session)
    solution = simulator.submit({}, is_blocking=False)
    target = tmp_path / "queued.json"
    solution.dump(target)
    assert json.loads(target.read_text())["result"] is None

    # Metadata-only restores remain offline until both URL and key are supplied.
    restored = Simulator.restore(target)
    with pytest.raises(DandeliionAPIException, match="offline"):
        _ = restored.status
    with pytest.raises(DandeliionInterfaceException):
        Simulator.restore(target, api_key=TOKEN)


def test_failed_download_preserves_existing_target(tmp_path):
    """Leave an existing target intact after a streamed length mismatch."""
    result = b'{"Solution":{"Time [s]":[0]}}'
    target = tmp_path / "solution.json"
    target.write_text("existing")
    session = FakeSession(
        FakeResponse(
            status_code=202,
            json_data=run_payload("succeeded", result_size=len(result)),
        ),
        FakeResponse(
            status_code=200,
            json_data={"offset": 0, "next_offset": 0, "eof": True, "text": ""},
        ),
        FakeResponse(
            status_code=200,
            body=result,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(result) + 1),
            },
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException, match="Content-Length"):
        solution.dump(target)
    assert target.read_text() == "existing"
    assert not list(tmp_path.glob(".solution.json.*.tmp"))


def test_restore_rejects_v1_and_corrupt_bundles(tmp_path):
    """Reject legacy restore objects and syntactically invalid JSON bundles."""
    # Client 2.0 intentionally has no migration path for v1 restore files.
    v1 = tmp_path / "v1.json"
    v1.write_text(json.dumps({"Run": {"id": "old"}}))
    with pytest.raises(DandeliionInterfaceException, match="Unsupported v1"):
        Simulator.restore(v1)

    # Corrupt JSON is reported as a bundle error rather than leaking parser errors.
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    with pytest.raises(DandeliionAPIException, match="valid JSON"):
        Simulator.restore(broken)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("id",), "not-a-uuid", "UUID"),
        (("status",), "success", "status"),
        (("backend",), "local", "backend"),
        (("provider_may_continue",), 0, "provider_may_continue"),
        (("created_at",), None, "created_at"),
        (("provider_started_at",), 1, "provider_started_at"),
        (("portal_validation", "valid"), "yes", "token validation"),
        (("artifacts", "result_size"), -1, "result_size"),
        (("artifacts", "solution_fields"), "not-a-list", "solution field"),
        (("artifacts", "solution_fields"), ["A", "A"], "duplicate"),
        (("artifacts", "expires_at"), 1, "artifact expiry"),
    ],
)
def test_run_schema_validation_edges(path, value, message):
    """Reject invalid values in every security-relevant run metadata field."""
    payload = run_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(DandeliionAPIException, match=message):
        _validate_run(payload, collection_url=RUNS_URL)


def test_run_schema_rejects_nonobjects_and_wrong_ids():
    """Require object metadata, the requested run ID, and URL context online."""
    with pytest.raises(DandeliionAPIException, match="expected an object"):
        _validate_run([], collection_url=RUNS_URL)
    with pytest.raises(DandeliionAPIException, match="was requested"):
        _validate_run(
            run_payload(),
            collection_url=RUNS_URL,
            expected_id="496a9ac5-a684-4eab-84b2-53626fd57655",
        )
    with pytest.raises(DandeliionAPIException, match="without an API URL"):
        _validate_run(run_payload(), collection_url=None)


@pytest.mark.parametrize(
    ("name", "url", "message"),
    [
        ("self", f"{RUNS_URL}/{RUN_ID}?query=1", "unsafe"),
        ("log", f"{RUNS_URL}/{RUN_ID}/wrong", "unexpected"),
    ],
)
def test_run_url_validation_edges(name, url, message):
    """Reject query-bearing or path-confused resource links from the API."""
    payload = run_payload()
    payload["urls"][name] = url
    with pytest.raises(DandeliionAPIException, match=message):
        _validate_run(payload, collection_url=RUNS_URL)


def test_default_https_port_is_same_origin():
    """Treat an explicit default HTTPS port as the trusted API origin."""
    payload = run_payload()
    payload["urls"] = {name: url.replace(API_ROOT, f"{API_ROOT}:443") for name, url in payload["urls"].items()}
    run = _validate_run(payload, collection_url=RUNS_URL)
    assert run["urls"]["self"] == f"{RUNS_URL}/{RUN_ID}"


def test_http_redirect_cross_origin_and_permanent_errors():
    """Refuse redirects and foreign origins while preserving permanent errors."""
    # Redirects are never followed, even if a server supplies a Location.
    redirect = FakeResponse(status_code=302, headers={"Location": "https://attacker.example"})
    with pytest.raises(DandeliionAPIException) as raised:
        Simulator(API_ROOT, TOKEN, max_attempts=1, _session=FakeSession(redirect))._request(
            "GET", RUNS_URL, expected_status={200}
        )
    assert raised.value.code == "redirect_refused"
    assert redirect.closed

    # The effective response URL must remain on the configured API origin.
    foreign = FakeResponse(status_code=200, url="https://attacker.example/api/v2/runs")
    with pytest.raises(DandeliionAPIException) as raised:
        Simulator(API_ROOT, TOKEN, _session=FakeSession(foreign))._request("GET", RUNS_URL, expected_status={200})
    assert raised.value.code == "cross_origin_response"

    # Non-retryable responses retain fallback messages and request identifiers.
    error = FakeResponse(
        status_code=418,
        json_data={"error": "short and stout"},
        reason="Teapot",
        headers={"X-Request-ID": "header-request"},
    )
    with pytest.raises(DandeliionAPIException) as raised:
        Simulator(API_ROOT, TOKEN, _session=FakeSession(error))._request("GET", RUNS_URL, expected_status={200})
    assert raised.value.status_code == 418
    assert "short and stout" in str(raised.value)
    assert raised.value.message == str(raised.value)
    assert raised.value.request_id == "header-request"


def test_retry_after_is_capped_and_invalid_value_falls_back(monkeypatch):
    """Cap numeric Retry-After delays and ignore invalid server values."""
    sleeps = []
    monkeypatch.setattr("dandeliion.client.simulator.time.sleep", sleeps.append)
    session = FakeSession(
        FakeResponse(
            status_code=429,
            json_data={"error": {"code": "limited", "message": "wait"}},
            headers={"Retry-After": "120"},
        ),
        FakeResponse(
            status_code=503,
            json_data={"error": {"code": "unavailable", "message": "wait"}},
            headers={"Retry-After": "tomorrow"},
        ),
        FakeResponse(status_code=200, json_data={}),
    )
    response = Simulator(API_ROOT, TOKEN, _session=session)._request("GET", RUNS_URL, expected_status={200})
    assert response.status_code == 200
    assert sleeps == [60.0, 1.0]
    assert Simulator._retry_after(FakeResponse(headers={"Retry-After": "nan"})) is None


def test_transport_exhaustion_invalid_token_and_offline_submit(monkeypatch):
    """Report exhausted transport retries and reject unusable submitters."""
    # Exhausting all configured transport attempts produces one structured error.
    monkeypatch.setattr("dandeliion.client.simulator.time.sleep", lambda _delay: None)
    simulator = Simulator(
        API_ROOT,
        TOKEN,
        max_attempts=2,
        _session=FakeSession(
            requests.Timeout("one"),
            requests.Timeout("two"),
        ),
    )
    with pytest.raises(DandeliionAPIException) as raised:
        simulator._request("GET", RUNS_URL, expected_status={200})
    assert raised.value.code == "transport_error"

    # Submission separately requires a valid token, online transport, and mapping body.
    with pytest.raises(DandeliionInterfaceException, match="64 lowercase"):
        Simulator(API_ROOT, "bad", _session=FakeSession()).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException, match="offline"):
        Simulator(None, None).submit({}, is_blocking=False)
    with pytest.raises(DandeliionInterfaceException, match="dictionary"):
        Simulator(API_ROOT, TOKEN, _session=FakeSession()).submit([], is_blocking=False)


def test_submit_rejects_bad_location_and_can_block(monkeypatch):
    """Validate submission Location headers and honor blocking submission mode."""
    # Accepted submissions cannot redirect run ownership to an untrusted origin.
    bad_location = FakeResponse(
        status_code=202,
        json_data=run_payload(),
        headers={"Location": "https://attacker.example/run"},
    )
    with pytest.raises(DandeliionAPIException, match="Location"):
        Simulator(API_ROOT, TOKEN, _session=FakeSession(bad_location)).submit({}, is_blocking=False)

    # Blocking submission joins the accepted solution without an overall timeout.
    joined = []
    monkeypatch.setattr(
        "dandeliion.client.solution.Solution.join",
        lambda self, timeout=None: joined.append((self.run_id, timeout)),
    )
    Simulator(
        API_ROOT,
        TOKEN,
        _session=FakeSession(FakeResponse(status_code=202, json_data=run_payload())),
    ).submit({})
    assert joined == [(RUN_ID, None)]


def test_refresh_join_and_result_state_edges():
    """Handle offline joins, terminal joins, failures, and expired artifacts."""
    # Non-terminal offline bundles can neither refresh nor wait for completion.
    queued = run_payload("queued")
    offline_solution = Solution(Simulator(None, None), _validate_run(queued, collection_url=None, require_urls=False))
    with pytest.raises(DandeliionAPIException, match="offline"):
        _ = offline_solution.status
    with pytest.raises(DandeliionAPIException, match="Cannot join"):
        offline_solution.join()
    with pytest.raises(DandeliionInterfaceException, match="non-negative"):
        Simulator(API_ROOT, TOKEN)._join(offline_solution, timeout=-1)

    # Joining an already-terminal success is an immediate no-op.
    succeeded = run_payload("succeeded")
    succeeded_solution = Solution(
        Simulator(None, None),
        _validate_run(succeeded, collection_url=None, require_urls=False),
    )
    succeeded_solution.join()

    # Failed runs expose their solver error when results are requested.
    failed = run_payload("failed")
    failed["error_code"] = "solver_failed"
    failed["error_message"] = "solver failed"
    failed_solution = Solution(
        Simulator(None, None),
        _validate_run(failed, collection_url=None, require_urls=False),
    )
    with pytest.raises(DandeliionAPIException) as raised:
        Simulator._ensure_succeeded(failed_solution)
    assert raised.value.code == "solver_failed"

    # Successful metadata is insufficient once retained artifacts are unavailable.
    unavailable = run_payload("succeeded", available=False)
    unavailable_solution = Solution(
        Simulator(None, None),
        _validate_run(unavailable, collection_url=None, require_urls=False),
    )
    with pytest.raises(DandeliionAPIException, match="no longer"):
        Simulator._ensure_succeeded(unavailable_solution)


def test_selected_result_validation_edges():
    """Reject unexpected, omitted, unavailable, and non-array selected fields."""
    # A selected response may not return fields the client did not request.
    unexpected = b'{"Solution":{"Other":[1]}}'
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("succeeded")),
        FakeResponse(status_code=200, body=unexpected),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException, match="unexpected"):
        solution._sim._fetch_fields(solution, ["Voltage [V]"])

    # Every requested field must be present in the streamed response.
    missing = b'{"Solution":{"Time [s]":[0]}}'
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("succeeded")),
        FakeResponse(status_code=200, body=missing),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException, match="omitted"):
        solution._sim._fetch_fields(solution, ["Time [s]", "Voltage [V]"])

    # Empty selections are local no-ops; non-empty offline selections fail clearly.
    assert solution._sim._fetch_fields(solution, []) == {}
    with pytest.raises(DandeliionAPIException, match="not connected"):
        Simulator(None, None)._fetch_fields(solution, ["Time [s]"])

    # Result fields must be numeric JSON arrays rather than scalar values.
    scalar = b'{"Solution":{"Voltage [V]":4.2}}'
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("succeeded")),
        FakeResponse(status_code=200, body=scalar),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException, match="JSON array"):
        solution._sim._fetch_fields(solution, ["Voltage [V]"])


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"offset": True, "next_offset": 0, "eof": True, "text": ""},
        {"offset": 0, "next_offset": -1, "eof": True, "text": ""},
        {"offset": 0, "next_offset": 0, "eof": "yes", "text": ""},
        {"offset": 0, "next_offset": 0, "eof": True, "text": 1},
        {"offset": 0, "next_offset": 0, "eof": False, "text": "duplicate"},
    ],
)
def test_log_validation_edges(payload):
    """Reject malformed incremental log pages and non-progressing content."""
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("running")),
        FakeResponse(status_code=200, json_data=payload),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException):
        _ = solution.log


def test_log_offset_cancel_and_dump_configuration_edges(tmp_path):
    """Reject mismatched log offsets, offline cancellation, and bad dump paths."""
    # Log pages must begin at the exact byte offset requested by the client.
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run_payload("running")),
        FakeResponse(
            status_code=200,
            json_data={"offset": 1, "next_offset": 1, "eof": True, "text": ""},
        ),
    )
    solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
    with pytest.raises(DandeliionAPIException, match="unexpected log offset"):
        _ = solution.log

    # Cancellation is impossible without an explicitly connected API transport.
    with pytest.raises(DandeliionAPIException, match="Cannot cancel"):
        Solution(
            Simulator(None, None), _validate_run(run_payload("running"), collection_url=None, require_urls=False)
        ).cancel()

    # Atomic dumps require an existing destination directory.
    with pytest.raises(DandeliionInterfaceException, match="directory"):
        solution.dump(tmp_path / "missing" / "solution.json")


def test_dump_rejects_bad_result_headers_and_sizes(tmp_path):
    """Reject unsafe result responses without replacing existing bundle files."""
    result = b'{"Solution":{"Time [s]":[0]}}'

    # Validate response metadata before accepting any streamed result bytes.
    cases = [
        FakeResponse(status_code=200, body=result, headers={"Content-Type": "text/plain"}),
        FakeResponse(status_code=200, body=b"", headers={"Content-Type": "application/json"}),
        FakeResponse(
            status_code=200,
            body=result,
            headers={"Content-Type": "application/json", "Content-Length": "bad"},
        ),
    ]
    messages = ["content type", "empty result", "Content-Length"]
    for index, (response, message) in enumerate(zip(cases, messages, strict=True)):
        run = run_payload("succeeded", result_size=None)
        session = FakeSession(
            FakeResponse(status_code=202, json_data=run),
            FakeResponse(
                status_code=200,
                json_data={"offset": 0, "next_offset": 0, "eof": True, "text": ""},
            ),
            response,
        )
        solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
        target = tmp_path / f"result-{index}.json"
        target.write_bytes(b"existing")
        with pytest.raises(DandeliionAPIException, match=message):
            solution.dump(target)
        assert target.read_bytes() == b"existing"

    # Validate the complete streamed JSON shape and advertised field order.
    invalid_results = [
        (b'{"Solution":{"Time [s]":0,"Voltage [V]":[4.2]}}', "not a JSON array"),
        (b'{"Solution":{"Time [s]":[0]}}', "do not match"),
        (b'{"Solution":', "invalid full-result JSON"),
    ]
    for index, (body, message) in enumerate(invalid_results):
        session = FakeSession(
            FakeResponse(
                status_code=202,
                json_data=run_payload("succeeded", result_size=len(body)),
            ),
            FakeResponse(
                status_code=200,
                json_data={"offset": 0, "next_offset": 0, "eof": True, "text": ""},
            ),
            FakeResponse(
                status_code=200,
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                },
            ),
        )
        target = tmp_path / f"invalid-result-{index}.json"
        target.write_bytes(b"existing")
        solution = Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False)
        with pytest.raises(DandeliionAPIException, match=message):
            solution.dump(target)
        assert target.read_bytes() == b"existing"


def test_offline_bundle_copy_and_bundle_result_validation(tmp_path):
    """Copy completed offline bundles and validate their top-level result value."""
    # A completed restore can be copied byte-for-byte or dumped onto itself.
    result = b'{"Solution":{"Time [s]":[0],"Voltage [V]":[4.2]}}'
    run = run_payload("succeeded", result_size=len(result))
    session = FakeSession(
        FakeResponse(status_code=202, json_data=run),
        FakeResponse(
            status_code=200,
            json_data={"offset": 0, "next_offset": 0, "eof": True, "text": ""},
        ),
        FakeResponse(
            status_code=200,
            body=result,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(result)),
            },
        ),
    )
    source = tmp_path / "source.json"
    Simulator(API_ROOT, TOKEN, _session=session).submit({}, is_blocking=False).dump(source)
    restored = Simulator.restore(source)
    copy = tmp_path / "copy.json"
    restored.dump(copy)
    assert copy.read_bytes() == source.read_bytes()
    restored.dump(source)

    # Bundle inspection distinguishes invalid scalar results from missing results.
    scalar = tmp_path / "scalar.json"
    scalar.write_text('{"result":1}')
    with pytest.raises(DandeliionAPIException, match="invalid result"):
        _bundle_has_result(scalar)
    missing = tmp_path / "missing-result.json"
    missing.write_text('{"format":"x"}')
    with pytest.raises(DandeliionAPIException, match="does not contain"):
        _bundle_has_result(missing)


def test_restore_bundle_metadata_validation(tmp_path):
    """Reject malformed client metadata, inconsistent results, and absent files."""
    base = {
        "format": "dandeliion-client-solution",
        "format_version": 2,
        "run": {key: value for key, value in run_payload("queued").items() if key != "urls"},
        "client": {"idempotency_key": "restore-key-001", "log_offset": 0},
        "log": "",
        "result": None,
    }

    # Validate each persisted client-owned metadata field independently.
    cases = [
        ("log", 1, "invalid log"),
        ("client", {"idempotency_key": "short", "log_offset": 0}, "idempotency"),
        ("client", {"idempotency_key": "restore-key-001", "log_offset": True}, "log offset"),
    ]
    for index, (key, value, message) in enumerate(cases):
        payload = deepcopy(base)
        payload[key] = value
        path = tmp_path / f"invalid-{index}.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(DandeliionAPIException, match=message):
            Simulator.restore(path)

    # A local result is valid only for a run persisted in the succeeded state.
    wrong_state = deepcopy(base)
    wrong_state["result"] = {"Solution": {}}
    path = tmp_path / "wrong-state.json"
    path.write_text(json.dumps(wrong_state))
    with pytest.raises(DandeliionAPIException, match="did not succeed"):
        Simulator.restore(path)

    # Missing paths fail as interface errors before bundle parsing begins.
    with pytest.raises(DandeliionInterfaceException, match="does not exist"):
        Simulator.restore(tmp_path / "absent.json")
