"""
@file tests/python/dandeliion/client/solve_test.py

Testing the solve routines in dandeliion.client
"""

#
# Copyright (C) 2024-2025 Dandeliion Team
#
# This library is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3.0 of the License, or (at your option)
# any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#

# built-in modules
import logging
import json
import pytest
from unittest import mock
from pathlib import Path

# custom modules
from dandeliion.client import solve, _convert_experiment
from dandeliion.client.experiment import Experiment as DandeLiionExperiment

# third-party modules
import pybamm
from bpx import parse_bpx_file
import numpy as np

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def input_bpx():
    """
    Fixture for default BPX
    """
    filename = Path(__file__).parent / 'data' / 'input_bpx.json'
    with open(filename, 'r') as f:
        params = json.load(f)
    params['Parameterisation']["User-defined"] = {}
    return filename, params


@pytest.fixture(scope='function')
def invalid_input_bpx():
    """
    Fixture for default BPX
    """
    filename = Path(__file__).parent / 'data' / 'invalid_input_bpx.json'
    with open(filename, 'r') as f:
        params = json.load(f)
    params['Parameterisation']["User-defined"] = {}
    return filename, params


@mock.patch('dandeliion.client._convert_experiment')
def test_solve_with_defaults(mock_convert, input_bpx):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    mock_convert.return_value = mock.Mock(), None

    experiment = mock.Mock(),

    solution = solve(
        simulator=mock_simulator,
        params=input_bpx[0],
        experiment=experiment
    )

    input_bpx[1]['Parameterisation']["User-defined"]['DandeLiion: Experiment'], _ = mock_convert.return_value

    assert len(mock_simulator.mock_calls) == 1
    mock_simulator.submit.assert_called_once_with(
        parameters=input_bpx[1],
        is_blocking=True,
    )
    assert solution == mock_simulator.submit.return_value


@mock.patch('dandeliion.client._convert_experiment')
def test_solve_with_time_series(mock_convert, input_bpx):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    mock_convert.return_value = mock.Mock(), {mock.Mock(): np.random.random_sample(10), mock.Mock(): np.random.random_sample(10)}

    experiment = mock.Mock(),

    solution = solve(
        simulator=mock_simulator,
        params=input_bpx[0],
        experiment=experiment
    )

    input_bpx[1]['Parameterisation']["User-defined"]['DandeLiion: Experiment'], \
        input_bpx[1]['Parameterisation']["User-defined"]['DandeLiion: Time series input'] = mock_convert.return_value

    assert len(mock_simulator.mock_calls) == 1
    mock_simulator.submit.assert_called_once_with(
        parameters=input_bpx[1],
        is_blocking=True,
    )
    assert solution == mock_simulator.submit.return_value


@pytest.mark.parametrize('is_blocking', [True, False])
@mock.patch('dandeliion.client._convert_experiment')
def test_solve_with_is_blocking(mock_convert, input_bpx, is_blocking):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    mock_convert.return_value = mock.Mock(), None

    experiment = mock.Mock(),

    solution = solve(
        simulator=mock_simulator,
        params=input_bpx[0],
        experiment=experiment,
        is_blocking=is_blocking,
    )

    input_bpx[1]['Parameterisation']["User-defined"]['DandeLiion: Experiment'], _ = mock_convert.return_value

    assert len(mock_simulator.mock_calls) == 1
    mock_simulator.submit.assert_called_once_with(
        parameters=input_bpx[1],
        is_blocking=is_blocking,
    )
    assert solution == mock_simulator.submit.return_value

    
@mock.patch('dandeliion.client._convert_experiment')
def test_solve_with_bpx_dict(mock_convert, input_bpx):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    mock_convert.return_value = mock.Mock(), None

    experiment = mock.Mock(),

    solution = solve(
        simulator=mock_simulator,
        params=input_bpx[1],
        experiment=experiment
    )

    input_bpx[1]['Parameterisation']["User-defined"]['DandeLiion: Experiment'], _ = mock_convert.return_value

    assert len(mock_simulator.mock_calls) == 1
    mock_simulator.submit.assert_called_once_with(
        parameters=input_bpx[1],
        is_blocking=True,
    )
    assert solution == mock_simulator.submit.return_value


@mock.patch('dandeliion.client._convert_experiment')
def test_solve_with_bpx_obj(mock_convert, input_bpx):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    mock_convert.return_value = mock.Mock(), None

    experiment = mock.Mock(),
    bpx = parse_bpx_file(input_bpx[0])

    solution = solve(
        simulator=mock_simulator,
        params=bpx,
        experiment=experiment
    )

    input_bpx[1]['Parameterisation']["User-defined"]['DandeLiion: Experiment'], _  = mock_convert.return_value

    assert len(mock_simulator.mock_calls) == 1
    mock_simulator.submit.assert_called_once_with(
        parameters=input_bpx[1],
        is_blocking=True,
    )
    assert solution == mock_simulator.submit.return_value


@mock.patch('dandeliion.client._convert_experiment')
def test_solve_with_extra_params(mock_convert, input_bpx):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    mock_convert.return_value = mock.Mock(), None

    extra_params = {
        'a': 'some value',
        'b': 'some other value',
    }
    experiment = mock.Mock(),

    solution = solve(
        simulator=mock_simulator,
        params=input_bpx[0],
        experiment=experiment,
        extra_params=extra_params,
    )
    input_bpx[1]['Parameterisation']['User-defined']['DandeLiion: Experiment'], _ = mock_convert.return_value
    for param, value in extra_params.items():
        input_bpx[1]['Parameterisation']['User-defined'][f'DandeLiion: {param}'] = value

    assert len(mock_simulator.mock_calls) == 1
    mock_simulator.submit.assert_called_once_with(
        parameters=input_bpx[1],
        is_blocking=True,
    )
    assert solution == mock_simulator.submit.return_value


def test_solve_with_invalid_params(invalid_input_bpx):
    """
    Test case for solve behaviour with invalid params
    """
    mock_simulator = mock.MagicMock()
    experiment = mock.Mock()

    # params are not valid bpx
    with pytest.raises(Exception):
        solve(
            simulator=mock_simulator,
            params=invalid_input_bpx[0],
            experiment=experiment
        )

    # params are not valid input type (e.g. list)
    with pytest.raises(ValueError):
        solve(
            simulator=mock_simulator,
            params=list(),
            experiment=experiment
        )


def test__convert_experiment_with_pybamm():
    """
    Tests conversion of pybamm Experiment into parameter dict
    """
    experiment = pybamm.Experiment(
        [
            (
                "Discharge at 10 A for 200 seconds",
                "Rest for 10 seconds",
                "Charge at 6 A for 100 seconds",
            )
        ]
        * 2,
        period="1 second",
    )
    converted_experiment, time_series = _convert_experiment(experiment)
    assert converted_experiment['Instructions'] == [
        "Discharge at 10 A for 200 seconds",
        "Rest for 10 seconds",
        "Charge at 6 A for 100 seconds",
    ] * 2
    assert time_series is None
    assert converted_experiment['Period'] == "1 second"
    assert converted_experiment['Temperature'] is None
    assert converted_experiment['Termination'] is None


@pytest.mark.parametrize('drive_cycle,drive_cycle_x,drive_cycle_y',  [
    (
        'power',
        ('Time [s]', np.linspace(0, 1, 60)),
        ('Power [W]', 0.5 * np.sin(2 * np.pi * np.linspace(0, 1, 60))),
    ),
    (
        'current',
        ('Time [s]', np.linspace(0, 1, 60)),
        ('Current [A]', np.linspace(0, 1, 60)),
    ),
])
def test__convert_experiment_with_drive_cycle(drive_cycle, drive_cycle_x, drive_cycle_y):
    """
    Tests conversion of pybamm Experiment into parameter dict with drive cycles
    """
    drive_cycle_step = getattr(pybamm.step, drive_cycle)(np.column_stack([drive_cycle_x[1], drive_cycle_y[1]]))
    
    experiment = pybamm.Experiment(
        [
            (
                "Discharge at 10 A for 200 seconds",
                "Rest for 10 seconds",
                "Charge at 6 A for 100 seconds",
                drive_cycle_step,
            ),
            drive_cycle_step,
        ]
        * 2,
        period="1 second",
    )
    converted_experiment, time_series = _convert_experiment(experiment)
    assert converted_experiment['Instructions'] == [
        "Discharge at 10 A for 200 seconds",
        "Rest for 10 seconds",
        "Charge at 6 A for 100 seconds",
        "Time series",
        "Time series",
    ] * 2
    np.testing.assert_equal(time_series, {
        drive_cycle_x[0]: drive_cycle_x[1],
        drive_cycle_y[0]: drive_cycle_y[1],
    })
    assert converted_experiment['Period'] == "1 second"
    assert converted_experiment['Temperature'] is None
    assert converted_experiment['Termination'] is None


@pytest.mark.parametrize('test_steps,expected_exception', [
    (
        [pybamm.step.power(1.0, duration=1.0),],
        TypeError,
    ),
    (
        [pybamm.step.BaseStep(np.column_stack([np.linspace(0, 1, 60), np.linspace(0, 1, 60)])),],
        TypeError,
    ),
    (
        [pybamm.step.current(np.column_stack([np.linspace(0, 1, 60), np.linspace(0, 1, 60)]), duration=2.0),],
        ValueError,
    ),
    (
        [pybamm.step.current(np.column_stack([np.linspace(0, 1, 60), np.linspace(0, 1, 60)])),
         pybamm.step.current(np.column_stack([np.linspace(0, 1, 30), np.linspace(0, 1, 30)])),],
        NotImplementedError,
    ),
])
def test__convert_experiment_with_pybamm_error(test_steps, expected_exception):
    """
    Tests conversion of invalid pybamm Experiment into parameter dict
    """
    experiment = pybamm.Experiment(
        [
            *test_steps,
        ],
        period="1 second",
    )

    with pytest.raises(expected_exception):
        converted_experiment, time_series = _convert_experiment(experiment)


def test__convert_experiment_without_pybamm():
    """
    Tests conversion of DandeLiion Experiment into parameter dict
    """
    experiment = DandeLiionExperiment(
        [
            (
                "Discharge at 10 A for 200 seconds",
                "Rest for 10 seconds",
                "Charge at 6 A for 100 seconds",
                "Time series",
            )
        ]
        * 2,
        period="1 second",
    )
    converted_experiment, time_series = _convert_experiment(experiment)
    assert converted_experiment['Instructions'] == [
        "Discharge at 10 A for 200 seconds",
        "Rest for 10 seconds",
        "Charge at 6 A for 100 seconds",
        "Time series",
    ] * 2
    assert time_series is None
    assert converted_experiment['Period'] == "1 second"
    assert converted_experiment['Temperature'] is None
    assert converted_experiment['Termination'] is None

