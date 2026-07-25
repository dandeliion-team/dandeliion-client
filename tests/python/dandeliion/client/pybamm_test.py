# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import numpy as np
import pytest

pybamm = pytest.importorskip("pybamm")

from dandeliion.client import _convert_experiment  # noqa: E402


def test_convert_pybamm_experiment():
    experiment = pybamm.Experiment(
        ["Discharge at 1C for 1 hour", "Rest for 10 seconds"],
        period="5 seconds",
    )
    converted, time_series = _convert_experiment(experiment)
    assert converted["Instructions"] == [
        "Discharge at 1C for 1 hour",
        "Rest for 10 seconds",
    ]
    assert converted["Period"] == "5 seconds"
    assert time_series is None


@pytest.mark.parametrize("kind, field", [("current", "Current [A]"), ("power", "Power [W]")])
def test_convert_pybamm_drive_cycle(kind, field):
    drive_cycle = np.column_stack([np.array([0.0, 1.0, 2.0]), np.array([1.0, 0.5, 0.0])])
    step = getattr(pybamm.step, kind)(drive_cycle)
    converted, time_series = _convert_experiment(pybamm.Experiment([step]))
    assert converted["Instructions"] == ["Time series"]
    np.testing.assert_allclose(time_series["Time [s]"], drive_cycle[:, 0])
    np.testing.assert_allclose(time_series[field], drive_cycle[:, 1])
