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
from dandeliion.client.simulator import Simulator, DandeliionAPIException

logger = logging.getLogger(__name__)


class MockResponse:
    def __init__(self, json_data, status_code, reason=None):
        self.json_data = json_data
        self.status_code = status_code
        self.reason = reason

    def json(self):
        return self.json_data


@pytest.fixture(scope='function')
def mock_results():

    with open(Path(__file__).parent / 'data' / 'output.json', 'r') as f:
        return json.load(f)

@pytest.fixture(scope='function')
def mock_config():
    pass  # TODO


@mock.patch('dandeliion.client.solution.requests.post')
def test_fetch_single_data_column(mock_post):
    pass  # TODO


@mock.patch('dandeliion.client.solution.requests.post')
def test_fetch_multiple_data_columns(mock_post):
    pass  # TODO


@mock.patch('dandeliion.client.solution.requests.post')
def test_fetch_all_data_columns(mock_post):
    pass  # TODO


@mock.patch('dandeliion.client.solution.Solution.fetch_results')
def test_access_pre_fetched_data_column(mock_fetch):
    pass  # TODO


@mock.patch('dandeliion.client.solution.Solution.fetch_results')
def test_access_non_fetched_data_column(mock_fetch):
    pass  # TODO


@mock.patch('dandeliion.client.solution.Solution.fetch_results')
def test_access_non_existent_data_column(mock_fetch):
    pass  # TODO
