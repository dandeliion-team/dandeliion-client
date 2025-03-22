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
import copy
import pytest
from unittest import mock
from pathlib import Path

# custom modules
from dandeliion.client.simulator import Simulator, DandeliionAPIException

logger = logging.getLogger(__name__)


class MockResponse:
    """
    Class to create a mock requests.Response
    """
    def __init__(self, json_data, status_code, reason=None):
        self.json_data = json_data
        self.status_code = status_code
        self.reason = reason

    def json(self):
        return self.json_data


@pytest.fixture(scope='function')
def input_extended_bpx():
    """
    Fixture for a correct server submission data (BPX extended with Dandeliion-specific paras)
    """

    with open(Path(__file__).parent / 'data' / 'input_experiment.json', 'r') as f:
        return json.load(f)


@mock.patch('dandeliion.client.simulator.requests.post')
def test_submit_non_blocking(mock_post, input_extended_bpx):
    """
    Test case for a non-blocking submit
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    mock_server_return = {'Run': {'ws_status_url': mock.Mock(), 'id': mock.Mock()}}

    mock_post.return_value = MockResponse(json_data=mock_server_return, status_code=200)

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    solution = simulator.submit(input_extended_bpx, is_blocking=False)

    # check that REST API was called with correct values
    mock_post.assert_called_once_with(
        url=mock_url,
        json=input_extended_bpx,
        headers={'Authorization': f'Token {mock_api_key}'},
    )

    # check that solution is created correctly from returned run info
    assert solution._data['Run'] == mock_server_return['Run']


@mock.patch('dandeliion.client.simulator.SimulatorWebSocketClient')
@mock.patch('dandeliion.client.simulator.requests.post')
def test_submit_blocking(mock_post, mock_wsclient, input_extended_bpx, caplog):
    """
    Test case for a blocking submit
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    mock_server_return = {'Run': {'ws_status_url': mock.Mock(), 'id': mock.Mock(), 'status': 'success'}}
    mock_wsclient.return_value = mock.MagicMock()

    mock_post.return_value = MockResponse(json_data=mock_server_return, status_code=200)

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    simulator.submit(input_extended_bpx)

    # check that ws client was initialised correctly
    mock_wsclient.assert_called_once_with(
        url=mock_server_return['Run']['ws_status_url'],
        on_update=mock.ANY,
    )
    mock_wsclient.return_value.subscribe.assert_called_once_with(mock_server_return['Run']['id'], mock_api_key)
    # check if hook works as required (i.e. it updates the response_json and logs messages)
    assert mock_server_return['Run']['status'] == 'success'
    with caplog.at_level(logging.INFO):
        mock_wsclient.call_args[1]['on_update'](updates={'status': 'queued', 'log_message': 'some log message'})
    assert mock_server_return['Run']['status'] == 'queued'
    assert 'some log message' in caplog.text
    

@mock.patch('dandeliion.client.simulator.requests.post')
def test_submit_server_error(mock_post, input_extended_bpx):
    """
    Test case where server error happens during submit
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    mock_post.return_value = MockResponse(json_data='', status_code=400, reason='some reason')
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    with pytest.raises(DandeliionAPIException):
        simulator.submit(input_extended_bpx, is_blocking=False)


@mock.patch('dandeliion.client.simulator.requests.get')
def test_update_results_no_key_no_inline(mock_get):
    """
    Test case for calling update with no keys specified and explicit no inline
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {
        'Run': {'id': 42},
        'Solution': 'some solution',
    }
    prefetched_backup = copy.deepcopy(prefetched_data)
    returned_data = copy.deepcopy(prefetched_data)
    returned_data['Solution'] = 'some other solution'
    mock_get.return_value = MockResponse(json_data=returned_data, status_code=200)

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    fetched = simulator.update_results(prefetched_data, inline=False)

    # check that correct params & header were submitted to server
    mock_get.assert_called_once_with(
        url=mock_url,
        params=[('id', prefetched_data['Run']['id'])],
        headers={'Authorization': f'Token {mock_api_key}'},
    )

    # check that prefetched data was not altered
    assert prefetched_data == prefetched_backup

    # check that returned data is fetched data
    assert fetched == returned_data


@mock.patch('dandeliion.client.simulator.requests.get')
def test_update_results_with_keys(mock_get):
    """
    Test case for calling update on a set of keys with default inline (i.e. no inline)
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {
        'Run': {'id': 42},
        'Solution': 'some solution',
    }
    prefetched_backup = copy.deepcopy(prefetched_data)
    returned_data = copy.deepcopy(prefetched_data)
    returned_data['Solution'] = 'some other solution'
    mock_get.return_value = MockResponse(json_data=returned_data, status_code=200)
    keys = [mock.Mock(), mock.Mock(), mock.Mock()]

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    fetched = simulator.update_results(prefetched_data, keys=keys)

    # check that correct params & header were submitted to server
    mock_get.assert_called_once_with(
        url=mock_url,
        params=[*[('key', key) for key in keys], ('id', prefetched_data['Run']['id'])],
        headers={'Authorization': f'Token {mock_api_key}'},
    )

    # check that prefetched data was not altered
    assert prefetched_data == prefetched_backup

    # check that returned data is fetched data
    assert fetched == returned_data


@mock.patch('dandeliion.client.simulator.update_dict')
@mock.patch('dandeliion.client.simulator.requests.get')
def test_update_results_inline(mock_get, mock_update_dict):
    """
    Test case for calling update inline on passed data
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {
        'Run': {'id': 42},
        'Solution': 'some solution',
    }
    prefetched_backup = copy.deepcopy(prefetched_data)
    returned_data = copy.deepcopy(prefetched_data)
    returned_data['Solution'] = 'some other solution'
    mock_get.return_value = MockResponse(json_data=returned_data, status_code=200)
    mock_update_dict.return_value = mock.Mock()

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    simulator.update_results(prefetched_data, inline=True)

    # check that update_dict was used with prefetched and fetched data
    mock_update_dict.assert_called_once_with(
        prefetched_backup,
        returned_data,
    )


@mock.patch('dandeliion.client.simulator.requests.get')
def test_update_results_with_incorrect_id(mock_get):
    """
    Test case for calling update and receiving incorrect run
    """
    prefetched_data = {
        'Run': {'id': mock.Mock()},
    }
    returned_data = {
        'Run': {'id': mock.Mock()},  # this is a different mock
    }
    mock_get.return_value = MockResponse(json_data=returned_data, status_code=200)

    simulator = Simulator(api_url=mock.Mock(), api_key=mock.Mock())
    with pytest.raises(DandeliionAPIException):
        simulator.update_results(prefetched_data)


@mock.patch('dandeliion.client.simulator.requests.get')
def test_update_results_with_server_error(mock_get):
    """
    Test case for calling update with server error
    """
    prefetched_data = {
        'Run': {'id': mock.Mock()},
    }
    mock_get.return_value = MockResponse(json_data='', status_code=400, reason='some reason')

    simulator = Simulator(api_url=mock.Mock(), api_key=mock.Mock())
    with pytest.raises(DandeliionAPIException):
        simulator.update_results(prefetched_data)


@mock.patch('dandeliion.client.simulator.Simulator.update_results')
@pytest.mark.parametrize("status", ['success', 'failed'])
def test_get_status_when_finished(mock_update, status):
    """
    Test case for getting status of run for an already finished run
    """
    prefetched_data = {
        'Run': {'status': status},
    }
    simulator = Simulator(api_url=mock.Mock(), api_key=mock.Mock())
    returned_status = simulator.get_status(prefetched_data)

    assert returned_status == status
    # update should have not been called in these cases
    mock_update.assert_not_called()


@mock.patch('dandeliion.client.simulator.Simulator.update_results')
@pytest.mark.parametrize("status", ['queued', 'running'])
def test_get_status_when_running(mock_update, status):
    """
    Test case for getting status of run for an already finished run
    """
    prefetched_data = {
        'Run': {'status': status},
    }
    simulator = Simulator(api_url=mock.Mock(), api_key=mock.Mock())
    simulator.get_status(prefetched_data)

    # update should have not been called in these cases
    mock_update.assert_called_once_with(
        prefetched_data,
        inline=True,
    )
