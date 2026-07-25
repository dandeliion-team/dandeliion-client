# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from unittest import mock

import numpy as np
import pytest
from dandeliion.client import DandeliionAPIException
from dandeliion.client.solution import InterpolatedArray, Solution

RUN_ID = "7ad965d1-7c66-47eb-b095-25a2c4c52f0f"


def run(status="succeeded", fields=None):
    return {
        "id": RUN_ID,
        "status": status,
        "backend": "lambda",
        "error_code": "",
        "error_message": "",
        "portal_validation": {
            "valid": True,
            "status": "valid",
            "expires_at": "2027-01-01T00:00:00Z",
            "uses_remaining": 2,
            "error": None,
        },
        "artifacts": {
            "available": status == "succeeded",
            "result_size": 1,
            "solution_fields": fields or ["Time [s]", "Voltage [V]"],
            "expires_at": None,
            "purged_at": None,
        },
        "urls": {
            "self": "self",
            "result": "result",
            "log": "log",
            "cancel": "cancel",
        },
    }


def simulator_with_fields():
    simulator = mock.MagicMock()
    simulator._fetch_fields.return_value = {
        "Time [s]": np.array([0.0, 1.0, 2.0]),
        "Voltage [V]": np.array([4.2, 4.1, 4.0]),
    }
    return simulator


def test_mapping_fetches_only_missing_fields_and_caches():
    simulator = simulator_with_fields()
    solution = Solution(simulator, run(), time_column="Time [s]")

    first = solution["Voltage [V]"]
    second = solution["Voltage [V]"]

    assert isinstance(first, InterpolatedArray)
    assert first(t=0.5) == pytest.approx(4.15)
    np.testing.assert_allclose(second, first)
    simulator._fetch_fields.assert_called_once_with(
        solution,
        ["Time [s]", "Voltage [V]"],
    )
    assert list(solution) == ["Time [s]", "Voltage [V]"]
    assert len(solution) == 2


def test_returned_arrays_do_not_mutate_cached_values():
    simulator = simulator_with_fields()
    solution = Solution(simulator, run(), time_column="Time [s]")
    values = solution["Voltage [V]"]
    values[0] = 0
    assert solution["Voltage [V]"][0] == pytest.approx(4.2)


def test_interpolated_array_preserves_metadata_on_views():
    values = InterpolatedArray([0, 1, 2], [4.2, 4.1, 4.0])
    sliced = values[1:]
    assert sliced.t is not None
    np.testing.assert_array_equal(sliced.t, [1, 2])
    assert sliced(t=1.5) == pytest.approx(4.05)


def test_multidimensional_fields_return_plain_arrays():
    simulator = mock.MagicMock()
    simulator._fetch_fields.return_value = {
        "Time [s]": np.array([0.0, 1.0]),
        "Field": np.array([[1.0, 2.0], [3.0, 4.0]]),
    }
    solution = Solution(
        simulator,
        run(fields=["Time [s]", "Field"]),
        time_column="Time [s]",
    )
    assert not isinstance(solution["Field"], InterpolatedArray)


def test_unknown_and_not_ready_fields_raise_clear_errors():
    simulator = simulator_with_fields()
    solution = Solution(simulator, run(), time_column="Time [s]")
    with pytest.raises(KeyError):
        _ = solution["Unknown"]

    queued = run("queued")
    simulator._get_status.return_value = "queued"
    with pytest.raises(DandeliionAPIException, match="Solution not ready"):
        _ = Solution(simulator, queued)["Voltage [V]"]


def test_status_log_join_cancel_and_dump_delegate():
    simulator = mock.MagicMock()
    simulator._get_status.return_value = "running"
    simulator._get_log.return_value = "log"
    simulator._cancel.return_value = "cancel_requested"
    solution = Solution(simulator, run("running"))

    assert solution.status == "running"
    assert solution.log == "log"
    solution.join(timeout=12)
    assert solution.cancel() == "cancel_requested"
    solution.dump("solution.json")

    simulator._get_status.assert_called_once_with(solution)
    simulator._get_log.assert_called_once_with(solution)
    simulator._join.assert_called_once_with(solution, 12)
    simulator._cancel.assert_called_once_with(solution)
    simulator._dump.assert_called_once_with(solution, "solution.json")


def test_token_validation_and_identifiers():
    solution = Solution(
        simulator_with_fields(),
        run(),
        idempotency_key="request-0001",
    )
    assert solution.run_id == RUN_ID
    assert solution.idempotency_key == "request-0001"
    assert solution.token_validation.status == "valid"
    assert solution.token_validation.uses_remaining == 2


def test_plain_array_mode_and_interpolation_validation():
    simulator = simulator_with_fields()
    solution = Solution(simulator, run(), time_column=None)
    values = solution["Voltage [V]"]
    assert isinstance(values, np.ndarray)
    assert not isinstance(values, InterpolatedArray)

    with pytest.raises(ValueError, match="one-dimensional"):
        InterpolatedArray([0, 1], [[1, 2], [3, 4]])
    with pytest.raises(ValueError, match="same length"):
        InterpolatedArray([0], [1, 2])
    with pytest.raises(ValueError, match="one-dimensional"):
        InterpolatedArray([0, 1], [1, 2]).reshape((1, 2))(t=0.5)


def test_missing_time_field_and_invalid_field_metadata():
    simulator = mock.MagicMock()
    simulator._fetch_fields.return_value = {"Voltage [V]": np.array([4.2])}
    solution = Solution(
        simulator,
        run(fields=["Voltage [V]"]),
        time_column="Time [s]",
    )
    with pytest.raises(DandeliionAPIException, match="required time"):
        _ = solution["Voltage [V]"]

    invalid = run()
    invalid["artifacts"]["solution_fields"] = "invalid"
    with pytest.raises(DandeliionAPIException, match="invalid solution fields"):
        len(Solution(simulator, invalid))


def test_invalid_or_absent_token_metadata():
    no_token = run()
    no_token["portal_validation"] = {}
    assert Solution(simulator_with_fields(), no_token).token_validation is None

    bad_token = run()
    bad_token["portal_validation"] = {"valid": True}
    with pytest.raises(DandeliionAPIException, match="invalid token"):
        _ = Solution(simulator_with_fields(), bad_token).token_validation


def test_local_result_errors_and_cached_load(tmp_path):
    simulator = simulator_with_fields()
    missing_path = tmp_path / "missing.json"
    solution = Solution(
        simulator,
        run(),
        bundle_path=missing_path,
        local_result=True,
        time_column="Time [s]",
    )
    with pytest.raises(DandeliionAPIException, match="invalid solution data"):
        _ = solution["Voltage [V]"]

    omitted = tmp_path / "omitted.json"
    omitted.write_text('{"result":{"Solution":{"Time [s]":[0]}}}')
    solution = Solution(
        simulator,
        run(),
        bundle_path=omitted,
        local_result=True,
        time_column="Time [s]",
    )
    with pytest.raises(DandeliionAPIException, match="omits"):
        _ = solution["Voltage [V]"]

    solution._fields["Time [s]"] = np.array([0.0])
    solution._load_fields(["Time [s]"])
