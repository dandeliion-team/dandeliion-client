# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from bpx import parse_bpx_file
from dandeliion.client import _convert_experiment, solve
from dandeliion.client.experiment import Experiment


@pytest.fixture
def input_bpx():
    filename = Path(__file__).parent / "data" / "input_bpx.json"
    payload = json.loads(filename.read_text())
    payload["Parameterisation"]["User-defined"] = {}
    return filename, payload


def test_solve_accepts_path_dict_and_bpx(input_bpx):
    for parameters in (input_bpx[0], input_bpx[1], parse_bpx_file(input_bpx[0])):
        simulator = mock.MagicMock()
        returned = solve(simulator, parameters, is_blocking=False)
        assert returned is simulator.submit.return_value
        submitted = simulator.submit.call_args.kwargs
        assert submitted["parameters"]["Parameterisation"]["User-defined"] == {}
        assert submitted["is_blocking"] is False
        assert submitted["idempotency_key"] is None


def test_solve_adds_experiment_extra_parameters_and_idempotency(input_bpx):
    simulator = mock.MagicMock()
    experiment = Experiment(
        ["Discharge at 1C for 1 hour"],
        period="10 seconds",
    )

    solve(
        simulator,
        input_bpx[0],
        experiment=experiment,
        extra_params={"Initial SOC": 0.5},
        idempotency_key="solve-key-0001",
    )

    submitted = simulator.submit.call_args.kwargs
    user_defined = submitted["parameters"]["Parameterisation"]["User-defined"]
    assert user_defined["DandeLiion: Initial SOC"] == 0.5
    assert user_defined["DandeLiion: Experiment"]["Instructions"] == ["Discharge at 1C for 1 hour"]
    assert submitted["idempotency_key"] == "solve-key-0001"


def test_convert_local_experiment():
    experiment = Experiment(
        [("Discharge at 1C for 1 hour", "Rest for 10 seconds")],
        period="5 seconds",
        temperature="25oC",
        termination="2.5 V",
    )
    converted, time_series = _convert_experiment(experiment)
    assert converted == {
        "Instructions": ["Discharge at 1C for 1 hour", "Rest for 10 seconds"],
        "Period": "5 seconds",
        "Temperature": "25oC",
        "Termination": "2.5 V",
    }
    assert time_series is None


def test_solve_rejects_invalid_inputs(tmp_path):
    simulator = mock.MagicMock()
    with pytest.raises(ValueError):
        solve(simulator, [])
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}")
    with pytest.raises(ValueError):
        solve(simulator, invalid)


def test_numpy_drive_cycle_values_are_serialized(input_bpx, monkeypatch):
    simulator = mock.MagicMock()
    experiment = mock.Mock()
    monkeypatch.setattr(
        "dandeliion.client._convert_experiment",
        lambda experiment, time_series=None: (
            {"Instructions": ["Time series"]},
            {
                "Time [s]": np.array([0.0, 1.0]),
                "Current [A]": np.array([1.0, 1.0]),
            },
        ),
    )
    solve(simulator, input_bpx[0], experiment=experiment)
    series = simulator.submit.call_args.kwargs["parameters"]["Parameterisation"]["User-defined"][
        "DandeLiion: Time series input"
    ]
    assert series == {"Time [s]": [0.0, 1.0], "Current [A]": [1.0, 1.0]}
