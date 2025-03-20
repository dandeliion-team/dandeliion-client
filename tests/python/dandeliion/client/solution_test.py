"""
@file tests/python/dandeliion/client/simulator_test.py

Testing the routines for dandeliion.client.Simulator
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
from dandeliion.client.solution import Solution, InterpolatedArray, DandeliionAPIException

# third-party modules
import numpy as np

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def mock_results():

    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('field', ['Time [s]', 'Electrolyte potential [V]'])
def test_access_prefetched_data_column(field):
    """
    Test case for accessing prefetched data (without defined time column)
    """
    mock_simulator = mock.MagicMock()
    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        prefetched_data = json.load(f)

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    data = solution[field]
    assert len(mock_simulator.mock_calls) == 0
    assert np.array_equal(data, prefetched_data['Solution'][field])
    assert not isinstance(data, InterpolatedArray)


@pytest.mark.parametrize('field,valid', [('Current [A]', True), ('Electrolyte potential [V]', False), ('Electrolyte x-coordinate [m]', False)])
def test_access_prefetched_data_column_with_time_column(field, valid):
    """
    Test case for accessing prefetched data with defined time column (with valid time series and without)
    """
    mock_simulator = mock.MagicMock()
    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        prefetched_data = json.load(f)

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data, time_column='Time [s]')
    data = solution[field]
    assert len(mock_simulator.mock_calls) == 0
    assert np.array_equal(data, prefetched_data['Solution'][field])
    assert isinstance(data, InterpolatedArray)
    if valid:
        solution[field](t=42)
    else:
        with pytest.raises(ValueError):
            solution[field](t=42)


def test_access_non_prefetched_data_column():
    """
    Test case for accessing non-prefetched data
    """
    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        prefetched_data = json.load(f)

    solution_data = prefetched_data.pop('Solution')
    prefetched_data['Solution'] = {name: None for name, _ in solution_data.items()}

    field = "Time [s]"

    def mock_update(data, keys, inline=True):
        for key in keys:
            data['Solution'][key] = solution_data[key]

    mock_simulator = mock.MagicMock()
    mock_simulator.update_results = mock_update

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    data = solution[field]
    assert np.array_equal(data, solution_data[field])


def test_access_non_existent_data_column():
    """
    Test case for accessing non-existent result column
    """
    mock_simulator = mock.MagicMock()
    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        prefetched_data = json.load(f)

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    field = "Non-Existing Field"
    with pytest.raises(KeyError):
        solution[field]


@pytest.mark.parametrize("fct,args", [('keys', []), ('items', []), ('values', []),  ('__iter__', []), ])
@mock.patch('dandeliion.client.solution.Solution._init_solution')
def test_dict_functions(mock_init, fct, args):
    """
    Test case for various dict functions for solutions (keys, values, items, etc)
    """
    mock_simulator = mock.MagicMock()
    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        prefetched_data = json.load(f)

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    mock_init.assert_not_called()
    if fct == 'values':
        assert np.all([np.array_equal(x, y) for x, y in zip(
            list(getattr(prefetched_data['Solution'], fct)(*args)),
            list(getattr(solution, fct)(*args)),
        )])
    elif fct == 'items':
        assert np.all([np.array_equal(x, y) and k1 == k2 for (k1, x), (k2, y) in zip(
            list(getattr(prefetched_data['Solution'], fct)(*args)),
            list(getattr(solution, fct)(*args)),
        )])
    else:
        assert list(getattr(prefetched_data['Solution'], fct)(*args)) == list(getattr(solution, fct)(*args))
    mock_init.assert_not_called()


@pytest.mark.parametrize("fct,args", [('keys', []), ('items', []), ('values', []),  ('__iter__', []),])
@mock.patch('dandeliion.client.solution.Solution._init_solution')
def test_dict_functions_with_init(mock_init, fct, args):
    """
    Test case for various dict functions for solutions with uninitialised solutions (so initialising first)
    """
    mock_simulator = mock.MagicMock()
    prefetched_data = {}

    def mock_init_solution():
        prefetched_data['Solution'] = {}

    with mock.patch("dandeliion.client.solution.Solution._init_solution", wraps=mock_init_solution) as mock_init:
        solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
        mock_init.assert_not_called()
        list(getattr(solution, fct)(*args))
        mock_init.assert_called_once_with()


def test_init_solution():
    """
    Test case for various dict functions for solutions with uninitialised solutions (so initialising first)
    """
    mock_simulator = mock.MagicMock()
    prefetched_data = {'Solution': None}

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    with pytest.raises(DandeliionAPIException):
        solution._init_solution()
    mock_simulator.update_results.assert_called_once_with(
        prefetched_data,
        inline=True,
    )


def test_status():
    """
    Test case for various dict functions for solutions with uninitialised solutions (so initialising first)
    """
    mock_simulator = mock.MagicMock()
    prefetched_data = mock.Mock()

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    assert solution.status == mock_simulator.get_status.return_value
    mock_simulator.get_status.assert_called_once_with(
        prefetched_data
    )
