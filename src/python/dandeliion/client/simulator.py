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
from pathlib import Path
from typing import Optional, Union

# custom modules
from .tools.misc import update_dict
from .websocket import SimulatorWebSocketClient
from .exceptions import DandeliionAPIException
from .solution import Solution

logger = logging.getLogger(__name__)


@dataclass
class Simulator:

    """
    Simulator class that stores authentication details and deals with job submission and result acquisition
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

        run_id = response_json['Run']['id']
        data = update_dict(parameters, response_json, inline=False)

        if is_blocking:
            cond = threading.Condition()

            def task_update_signal_hook(updates):
                logger.debug(f'update_signal_hook triggered with: {updates}')
                with cond:
                    data['Run']['status'] = updates['status']
                    data['log_update'] = updates['log_update']
                    logger.info(f"[{updates['status']}] | {updates['log_update']}")

                    cond.notify_all()
                    logger.debug('all notified')

            client = SimulatorWebSocketClient(
                url=data['Run']['ws_status_url'],
                on_update=task_update_signal_hook,
            )
            client.subscribe(run_id, self.api_key)
            while data['Run']['status'] in ['queued', 'running']:
                # block until task update signalled
                with cond:
                    cond.wait()
            # closing connection again
            client.close()

        return Solution(sim=self, prefetched_data=data, time_column='Time [s]')

    def update_results(self, prefetched_data: dict, keys: list = None, inline: bool = False) -> Optional[dict]:
        """
        Function to (pre)fetch result columns from server and update/append prefetched_data
        """
        params = [('key', key) for key in keys] if keys is not None else []
        params.append(('id', prefetched_data['Run']['id']))

        headers = {'Authorization': f'Token {self.api_key}'}
        response = requests.get(url=self.api_url, params=params, headers=headers)
        if response.status_code >= 400:
            raise DandeliionAPIException(f"Your request has failed: {response.reason}. Try again?")

        response_json = response.json()
        # sanity check if id for sim returned is same as the one requested
        if response_json['Run']['id'] != prefetched_data['Run']['id']:
            raise DandeliionAPIException(
                "Something went wrong."
                f" Reported run id is {response_json['Run']['id']}"
                f" (requested: {prefetched_data['Run']['id']})"
            )

        if inline:
            update_dict(prefetched_data, response.json())
        else:
            return response.json()

    def get_status(self, prefetched_data: dict) -> str:
        """
        Returns current status of a simulation (as either stored in prefetched_data
        if finished/failed or retrieved from server if potentially still queued/running)
        """
        if prefetched_data['Run']['status'] in ['queued', 'running']:
            self.update_results(prefetched_data, inline=True)
        return prefetched_data['Run']['status']

    def get_log(self, prefetched_data: dict) -> str:
        """
        Returns log file
        """
        headers = {'Authorization': f'Token {self.api_key}'}
        params = []
        params.append(('id', prefetched_data['Run']['id']))

        # fetch log if not done so yet; refetch it if simulation is not finished yet
        if (prefetched_data['Run']['status'] in ['queued', 'running'] or 'Log' not in prefetched_data):
            response = requests.get(f"{self.api_url}/log", params=params, headers=headers)

            if response.status_code >= 400:
                raise DandeliionAPIException(
                    f"Error code {response.status_code}. Failed to fetch log: {response.reason}"
                )

        # not buffering log; will change anyway; just return response
        if prefetched_data['Run']['status'] in ['queued', 'running']:
            return response.text

        # store final version of log in buffer if not exists yet
        if 'Log' not in prefetched_data:
            prefetched_data['Log'] = response.text

        return prefetched_data['Log']

    @classmethod
    def restore(cls, filepath: Union[str, Path], api_url=None, api_key=None):
        """Loads prefetched/solution data and creates new solution object.
        If api url/key provided (optional), it will also try to connect to server for updates
        for this simulation (e.g. if stored before finished)

        Args:
           filepath (str | Path): path to file were data should be loaded from
           api_url (str): url to server where simulation was run
           api_key (str): api key used to run this simulation
        """
        sim = cls(api_url=api_url, api_key=api_key)
        return Solution(sim=sim, prefetched_data=filepath, time_column='Time [s]')
