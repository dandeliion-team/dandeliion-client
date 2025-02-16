"""
@file python/dandeliion/client/simulator.py

module containing Dandeliion Simulator class
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
import requests
import threading
from dataclasses import dataclass

# custom modules
from .websocket import SimulatorWebSocketClient
from .exceptions import DandeliionAPIException
from .solution import Solution

logger = logging.getLogger(__name__)


@dataclass
class Simulator:

    """
    Simulator class that stores authentication details and deals with job submission
    """

    api_url: str
    api_key: str

    def submit(self, parameters: dict, is_blocking: bool = True):
        """
        Submit parameters to Simulator instance
        """

        # submit simulation to rest api
        headers = {'Authorization': f'Token {self.api_key}'}  # TODO adapt to server
        response = requests.post(url=self.api_url, json=parameters, headers=headers)
        if response.status_code >= 400:
            raise DandeliionAPIException(f"Your request has failed: {response.reason}")
        response_json = response.json()
        if is_blocking:
            cond = threading.Condition()

            def task_update_signal_hook(updates):
                with cond:
                    response_json['status'] = updates['status']
                    logger.info(updates['log_message'])
                    cond.notify_all()

            client = SimulatorWebSocketClient(
                url=response_json['ws_status_url'],
                api_key=self.api_key,
                on_update=task_update_signal_hook,
            )
            client.subscribe(response_json['id'])
            while response_json['status'] in ['Q', 'R']:
                # block until task update signalled
                with cond:
                    cond.wait()
            # closing connection again
            client.close()

        return Solution(response_json)
