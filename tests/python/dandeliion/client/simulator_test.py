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
def input_extended_bpx():

    with open(Path(__file__).parent / 'data' / 'input_experiment.json', 'r') as f:
        return json.load(f)


@mock.patch('dandeliion.client.simulator.requests.post')
def test_submit_non_blocking(mock_post, input_extended_bpx):
    mock_api_key = 'some_key'
    mock_url = 'test url'
    mock_server_return = {'ws_status_url': 'some config', 'id': 42}

    mock_post.return_value = MockResponse(json_data=mock_server_return, status_code=200)
    
    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    solution = simulator.submit(input_extended_bpx, is_blocking=False)

    # check that REST API was called with correct values
    mock_post.assert_called_once_with(
        url=mock_url,
        json=input_extended_bpx,
        headers={'Authorization': f'Token {mock_api_key}'},
    )

    # check that solution is created correctly from returned config
    assert solution._config == mock_server_return


@mock.patch('dandeliion.client.simulator.SimulatorWebSocketClient.__new__')
@mock.patch('dandeliion.client.simulator.requests.post')
def test_submit_blocking(mock_post, mock_wsclient, input_extended_bpx, caplog):
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    mock_server_return = {'ws_status_url': mock.Mock(), 'id': mock.Mock(), 'status': 'F'}
    mock_wsclient.return_value = mock.MagicMock()
    
    mock_post.return_value = MockResponse(json_data=mock_server_return, status_code=200)
    
    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    simulator.submit(input_extended_bpx)

    # check that ws client was initialised correctly    
    mock_wsclient.assert_called_once_with(
        mock.ANY,
        url=mock_server_return['ws_status_url'],
        api_key=mock_api_key,
        on_update=mock.ANY,
    )
    mock_wsclient.return_value.subscribe.assert_called_once_with(mock_server_return['id'])
    # check if hook works as required (i.e. it updates the response_json and logs messages)
    assert mock_server_return['status'] == 'F'
    with caplog.at_level(logging.INFO):
        mock_wsclient.call_args[1]['on_update'](updates={'status': 'Q', 'log_message': 'some log message'})
    assert mock_server_return['status'] == 'Q'
    assert 'some log message' in caplog.text


@mock.patch('dandeliion.client.simulator.requests.post')
def test_submit_server_error(mock_post, input_extended_bpx):
    mock_api_key = 'some_key'
    mock_url = 'test_url'
    mock_post.return_value = MockResponse(json_data='', status_code=400, reason='some reason')

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    with pytest.raises(DandeliionAPIException):
        simulator.submit(input_extended_bpx, is_blocking=False)
