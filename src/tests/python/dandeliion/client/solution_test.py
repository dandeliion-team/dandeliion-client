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
import requests
from pathlib import Path

# custom modules
from dandeliion.client.solution import Solution, DandeliionAPIException

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def mock_results():

    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        return json.load(f)


@pytest.mark.parametrize('field', ['Time [s]', 'Electrolyte potential [V]'])
def test_access_prefetched_data_column(field):
    """
    Test case for accessing prefetched data
    """
    mock_simulator = mock.MagicMock()
    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        prefetched_data = json.load(f)

    solution = Solution(sim=mock_simulator, prefetched_data=prefetched_data)
    data = solution[field]
    assert len(mock_simulator.mock_calls) == 0
    assert data == prefetched_data['Solution'][field]

    
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
    assert data == solution_data[field]


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
