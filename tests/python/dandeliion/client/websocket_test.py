"""
@file tests/python/dandeliion/client/websocket_test.py

Testing the routines for dandeliion.client.websocket
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
import json
import threading
from unittest import mock

# custom modules
from dandeliion.client import websocket


@mock.patch('dandeliion.client.websocket.websocket.WebSocketApp')
def test_client_creation(mock_wsc):

    url = mock.Mock()
    api_key = mock.Mock()

    def on_update(values: dict):
        return values

    client = websocket.SimulatorWebSocketClient(
        url=url,
        api_key=api_key,
        on_update=on_update,
    )

    mock_wsc.assert_called_once_with(
        url,
        on_open=mock.ANY,
        on_message=mock.ANY,
        on_error=mock.ANY,
        on_close=mock.ANY,
        header={'Authorization': f'Token {api_key}'},
    )

    assert client._is_opened is False
    client._on_open(client._app)
    assert client._is_opened is True


@mock.patch('dandeliion.client.websocket.websocket.WebSocketApp')
def test_client_subscribe(mock_wsc):

    url = mock.Mock()
    api_key = mock.Mock()

    def on_update(values: dict):
        return values

    client = websocket.SimulatorWebSocketClient(
        url=url,
        api_key=api_key,
        on_update=on_update,
    )

    run_id = mock.Mock()
    t = threading.Thread(target=client.subscribe, args=(run_id, ))
    t.start()
    client._on_open(client._app)
    t.join()
    mock_wsc.return_value.mock_calls
    mock_wsc.return_value.send.assert_called_once_with(run_id)
    print(mock_wsc.mock_calls)


@mock.patch('dandeliion.client.websocket.websocket.WebSocketApp')
def test_client_send_message(mock_wsc):

    url = mock.Mock()
    api_key = mock.Mock()

    def on_update(values: dict):
        return values

    client = websocket.SimulatorWebSocketClient(
        url=url,
        api_key=api_key,
        on_update=on_update,
    )
    
    message = mock.Mock()
    t = threading.Thread(target=client.send_message, args=(message, ))
    t.start()

    mock_wsc.return_value.send.assert_not_called()
    client._on_open(client._app)
    t.join()
    mock_wsc.return_value.send.assert_called_once_with(message)


@mock.patch('dandeliion.client.websocket.websocket.WebSocketApp')
def test_client_on_update(mock_wsc):

    url = mock.Mock()
    api_key = mock.Mock()
    on_update = mock.Mock()

    client = websocket.SimulatorWebSocketClient(
        url=url,
        api_key=api_key,
        on_update=on_update,
    )

    update_msg = json.dumps({'updates': 'some updates'})
    client._on_message(client._app, update_msg)

    on_update.assert_called_once_with('some updates')


@mock.patch('dandeliion.client.websocket.websocket.WebSocketApp')
def test_client_close(mock_wsc):

    url = mock.Mock()
    api_key = mock.Mock()
    on_update = mock.Mock()

    client = websocket.SimulatorWebSocketClient(
        url=url,
        api_key=api_key,
        on_update=on_update,
    )

    client.close()
    mock_wsc.return_value.close.assert_called_once()


@mock.patch('dandeliion.client.websocket.websocket.WebSocketApp')
def test_client_on_close(mock_wsc):

    url = mock.Mock()
    api_key = mock.Mock()
    on_update = mock.Mock()
    client = websocket.SimulatorWebSocketClient(
        url=url,
        api_key=api_key,
        on_update=on_update,
    )

    mock_close_status = mock.Mock()
    mock_close_message = mock.Mock()
    client._on_close(client._app, mock_close_status, mock_close_message)
    # TODO check logger messages?
