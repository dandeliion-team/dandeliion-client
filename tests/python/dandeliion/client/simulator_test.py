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
import filecmp
import logging
import json
import copy
import pytest
from unittest import mock
from pathlib import Path

# custom modules
from dandeliion.client.simulator import Simulator, Solution, DandeliionAPIException

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
@mock.patch('dandeliion.client.simulator.Simulator._join')
def test_submit_non_blocking(mock_join, mock_post, input_extended_bpx):
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

    # check that join was not called here
    mock_join.assert_not_called()


@mock.patch('dandeliion.client.simulator.requests.post')
@mock.patch('dandeliion.client.simulator.Simulator._join')
def test_submit_blocking(mock_join, mock_post, input_extended_bpx):
    """
    Test case for a blocking submit
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    mock_server_return ={'Run': {'ws_status_url': mock.Mock(), 'id': mock.Mock(), 'status': 'success'}}

    mock_post.return_value = MockResponse(json_data=mock_server_return, status_code=200)

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    simulator.submit(input_extended_bpx)

    input_extended_bpx.update(mock_server_return)
    mock_join.assert_called_once_with(input_extended_bpx)


class MockWSClient:
    def __init__(self, url, on_update):
        self.on_update = on_update

    def subscribe(self, run_id, api_key):
        import threading
        threading.Timer(
            interval=3.0,  # wait 3 sec before executing update
            function=self.on_update,
            args=({'status': 'success', 'log_update': 'some log message'},),
        ).start()

    def close(self):
        pass


@pytest.mark.timeout(60)  # prevents test from just getting stuck if update fails
@mock.patch('dandeliion.client.simulator.SimulatorWebSocketClient', MockWSClient)
def test__join(caplog):
    """
    Test case for _join helper function
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {'Run': {'ws_status_url': mock.Mock(), 'id': mock.Mock(), 'status': 'queued'}}

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    assert prefetched_data['Run']['status'] == 'queued'

    import time
    start_time = time.time()
    with caplog.at_level(logging.INFO):
        simulator._join(prefetched_data)
    # should have taken 3 seconds waiting time in mock client timer (+ a bit overhead)
    assert time.time() - start_time > 3.0

    # check if hook works as required (i.e. it updates the prefetched_data and log messages)
    assert prefetched_data['Run']['status'] == 'success'
    assert 'some log message' in caplog.text

    # second invocation should be instantanious (since sim already success)
    start_time = time.time()
    simulator._join(prefetched_data)
    assert time.time() - start_time < 0.1


@pytest.mark.timeout(60)  # prevents test from just getting stuck if update fails
@mock.patch('dandeliion.client.simulator.SimulatorWebSocketClient', MockWSClient)
def test__join_without_key(caplog):
    """
    Test case for _join helper function where api key is missing (e.g. not provided
    on restoring solution)
    """
    mock_url = mock.Mock()
    prefetched_data = {'Run': {'ws_status_url': mock.Mock(), 'id': mock.Mock(), 'status': 'queued'}}

    simulator = Simulator(api_url=mock_url, api_key=None)

    with pytest.raises(DandeliionAPIException):
        simulator._join(prefetched_data)


@mock.patch('dandeliion.client.simulator.requests.post')
@pytest.mark.parametrize("error", [
    (403, {'error': 'some error message'}, "some error message"),
    (403, "", "default reason"),
    (418, None, "default reason"),
])
def test_submit_server_error(mock_post, input_extended_bpx, error):
    """
    Test case where server error happens during submit
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    error_code, payload, expected_message = error
    mock_post.return_value = MockResponse(json_data=payload, status_code=error_code, reason='default reason')
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    with pytest.raises(DandeliionAPIException, match=f"Your request has failed: {error_code} - {expected_message}"):
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
def test_update_results_with_incomplete_simulator(mock_get):
    """
    Test case for calling update on an incomplete simulator
    e.g. from restoring a (partial) solution without connection credentials
    """
    id_ = mock.Mock()
    
    prefetched_data = {
        'Run': {'id': id_},
    }
    mock_get.return_value = MockResponse(json_data=prefetched_data, status_code=200)

    simulator = Simulator(api_url=None, api_key=mock.Mock())
    with pytest.raises(DandeliionAPIException):
        simulator.update_results(prefetched_data)


@mock.patch('dandeliion.client.simulator.requests.get')
@pytest.mark.parametrize("error", [
    (403, {'error': 'some error message'}, "some error message"),
    (403, "", "default reason"),
    (418, None, "default reason"),
])
def test_update_results_with_server_error(mock_get, error):
    """
    Test case for calling update with server error
    """
    error_code, payload, expected_message = error
    prefetched_data = {
        'Run': {'id': mock.Mock()},
    }
    mock_get.return_value = MockResponse(json_data=payload, status_code=error_code, reason="default reason")

    simulator = Simulator(api_url=mock.Mock(), api_key=mock.Mock())
    with pytest.raises(DandeliionAPIException, match=f"Your request has failed: {expected_message}. Try again?"):
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


@mock.patch('dandeliion.client.simulator.requests.get')
@pytest.mark.parametrize("status", ['queued', 'running'])
def test_get_log_success(mock_get, status):
    """
    Test case for getting log
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {'Run': {'id': 42, 'status': status}}
    expected_log = 'some log content'

    mock_get.return_value = mock.Mock(status_code=200, text=expected_log)

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    log = simulator.get_log(prefetched_data)

    mock_get.assert_called_once_with(
        f'{mock_url}/log',
        params=[('id', 42)],
        headers={'Authorization': f'Token {mock_api_key}'}
    )
    assert log == expected_log

@mock.patch('dandeliion.client.simulator.requests.get')
@pytest.mark.parametrize("status", ['queued', 'running'])
def test_get_log_empty_response(mock_get, status):
    """
    Test case for getting log where log file does not yet exist (returns an empty string)
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {'Run': {'id': 42, 'status': status}}

    mock_get.return_value = mock.Mock(status_code=200, text='')

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)
    log = simulator.get_log(prefetched_data)

    mock_get.assert_called_once_with(
        f'{mock_url}/log',
        params=[('id', 42)],
        headers={'Authorization': f'Token {mock_api_key}'}
    )
    assert log == ''


@mock.patch('dandeliion.client.simulator.requests.get')
@pytest.mark.parametrize("status", ['queued', 'running'])
def test_get_log_server_error(mock_get, status):
    """
    Test case for an error response getting log
    """
    mock_api_key = mock.Mock()
    mock_url = mock.Mock()
    prefetched_data = {'Run': {'id': 42, 'status': status}}

    mock_get.return_value = mock.Mock(status_code=404, reason='Not Found')

    simulator = Simulator(api_url=mock_url, api_key=mock_api_key)

    with pytest.raises(DandeliionAPIException) as e:
        simulator.get_log(prefetched_data)

    mock_get.assert_called_once_with(
        f'{mock_url}/log',
        params=[('id', 42)],
        headers={'Authorization': f'Token {mock_api_key}'}
    )
    assert 'Error code 404' in str(e.value)


def test_get_log_missing_id():
    """
    Test case for trying to get log with missing run id
    """
    simulator = Simulator(api_url='http://url', api_key='key')
    prefetched_data = {}  # no 'Run'

    with pytest.raises(KeyError):
        simulator.get_log(prefetched_data)


@pytest.mark.parametrize("mock_prefetched_data,is_update_called", [
    (Path(__file__).parent / "data"/ "output_server_finished.json", False),
    (Path(__file__).parent / "data"/ "output_server_unfinished.json", True),
])
@mock.patch('dandeliion.client.simulator.Simulator.update_results')
def test_dump_and_restore(mock_update, tmp_path, mock_prefetched_data, is_update_called):
    """
    Test case for saving and restoring solution for finished/unfinished run
    """
    mock_api_key = mock.Mock()

    sim = mock.Mock(spec=Simulator)
    solution = Solution(sim=sim, prefetched_data=mock_prefetched_data, time_column='Time [s]')

    output_file = tmp_path / "test_dump.json"
    solution.dump(output_file)
    # check if dumped file identical to the original file
    filecmp.cmp(mock_prefetched_data, output_file, shallow=False)

    solution_restored = Simulator.restore(output_file, api_key=mock_api_key)
    # check that update_results was (not) called
    if is_update_called:
        mock_update.assert_called_once()
    else:
        mock_update.assert_not_called()
    # check if content of restored solution is identical to previous solution
    assert solution_restored._data == solution._data
    # check if simulator of restored solution is set up correctly
    assert solution_restored._sim.api_key == mock_api_key
    assert solution_restored._sim.api_url == solution._data["Run"]["api_url"]
