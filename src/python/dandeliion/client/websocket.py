"""
@file src/python/dandeliion/client/websocket.py

Module for websocket client used in simulator
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
import threading
import json
import websocket
import logging
from threading import Condition
from collections.abc import Callable
from typing import Any


logger = logging.getLogger(__name__)


class SimulatorWebSocketClient:

    def __init__(self, url: str, api_key: str, on_update: Callable[[Any], None]):
        headers = {'Authorization': f'Token {api_key}'}  # TODO adapt to server

        self._app = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            header=headers,
        )

        self._on_update = on_update
        self._is_opened = False
        self._is_ready = Condition()

        # Initialise the run_forever inside a thread and make this thread as a daemon thread
        wst = threading.Thread(target=self._app.run_forever)
        # wst.daemon = True  # not needed anymore?
        wst.start()

    def send_message(self, message):
        with self._is_ready:
            self._is_ready.wait_for(lambda: self._is_opened)
        self._app.send(message)

    def subscribe(self, run_id):
        self.send_message(run_id)

    def close(self):
        self._app.close()

    def _on_open(self, wsapp):
        with self._is_ready:
            self._is_opened = True
            self._is_ready.notify_all()

    def _on_message(self, wsapp, message) -> None:
        self._on_update(json.loads(message)['updates'])

    def _on_close(self, wsapp, close_status_code, close_msg):
        # Because on_close was triggered, we know the opcode = 8
        logger.debug("on_close args:")
        logger.debug("close status code: " + str(close_status_code))
        logger.debug("close message: " + str(close_msg))

    def _on_error(self, wsapp, err):
        logger.error("ERROR", wsapp, err)
