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


@mock.patch('dandeliion.client.websocket.socketio.Client')
def test_client_creation(mock_wsc):

    url = (mock.Mock(), mock.Mock())
    api_key = mock.Mock()

    def on_update(values: dict):
        return values

    client = websocket.SimulatorWebSocketClient(
        url=url,
        on_update=on_update,
    )

    mock_wsc.return_value.connect.assert_called_once_with(
        url[0],
        namespaces=[url[1]],
    )
    mock_wsc.return_value.on('update', namespace=url[1])(on_update)


@mock.patch('dandeliion.client.websocket.socketio.Client')
def test_client_subscribe(mock_wsc):

    url = (mock.Mock(), mock.Mock())
    api_key = mock.Mock()

    def on_update(values: dict):
        return values

    client = websocket.SimulatorWebSocketClient(
        url=url,
        on_update=on_update,
    )

    run_id = mock.Mock()
    client.subscribe(run_id, api_key)
    mock_wsc.return_value.emit.assert_called_once_with('subscribe', (run_id, api_key), namespace=url[1])


@mock.patch('dandeliion.client.websocket.socketio.Client')
def test_client_close(mock_wsc):

    url = (mock.Mock(), mock.Mock())
    api_key = mock.Mock()
    on_update = mock.Mock()

    client = websocket.SimulatorWebSocketClient(
        url=url,
        on_update=on_update,
    )

    client.close()
    mock_wsc.return_value.shutdown.assert_called_once()
