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
import logging
from collections.abc import Callable
from typing import Any

# third-party modules
import socketio

logger = logging.getLogger(__name__)


class SimulatorWebSocketClient:

    def __init__(self, url: tuple[str, str], on_update: Callable[[Any], None]):
        server_url, self.namespace = url
        self._app = socketio.Client()
        self._app.connect(server_url, namespaces=[self.namespace])
        self._app.on(event='update', handler=on_update, namespace=self.namespace)

    def subscribe(self, id, api_key: str):
        self._app.emit('subscribe', (id, api_key), namespace=self.namespace)

    def close(self):
        self._app.shutdown()
