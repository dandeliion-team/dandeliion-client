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
import json
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


def get_error_message(response):
    """
    Extracts error message from error response
    """
    try:
        # Try to parse a JSON error message
        error_message = response.json()["error"]
    except (KeyError, ValueError, TypeError):
        # If response is not JSON (or expected field missing), fall back to reason text
        error_message = response.reason
    return error_message


@dataclass
class Simulator:

    """
    Simulator class that stores authentication details and deals with job submission and result acquisition

    Attributes:
        api_url (str): URL to server's API interface
        api_key (str): API key to access server
    """
    api_url: str
    api_key: str

    def submit(self, parameters: dict, is_blocking: bool = True) -> Solution:
        """
        Submit parameters to Simulator instance and returns Solution instance

        Args:
            parameters (dict): dictionary with all simulation parameters
            is_blocking (bool, optional): If True, function call will block until simulation is done,
                otherwise it will return instantly; default is True

        Returns:
            Solution: solution instance to access simulation status/results
        """

        # submit simulation to rest api
        headers = {'Authorization': f'Token {self.api_key}'}  # TODO adapt to server
        response = requests.post(url=self.api_url, json=parameters, headers=headers)
        if response.status_code >= 400:
            raise DandeliionAPIException(
                f"Your request has failed: {response.status_code} - {get_error_message(response)}"
            )
        response_json = response.json()
        data = update_dict(parameters, response_json, inline=False)
        if 'api_url' not in data['Run']:  # if not provided by server
            data['Run']['api_url'] = self.api_url

        solution = Solution(sim=self, prefetched_data=data, time_column='Time [s]')
        if is_blocking:
            solution.join()

        return solution

    def _join(self, prefetched_data: dict):
        """
        Blocks until simulation found in prefetched (meta)data is finished
        """
        if prefetched_data['Run']['status'] not in ['queued', 'running']:
            return

        if self.api_key is None:
            raise DandeliionAPIException(
                "You cannot join on this restored, incomplete simulation as "
                "there was no API key provided when restoring it."
            )

        cond = threading.Condition()

        def task_update_signal_hook(updates):
            logger.debug(f'update_signal_hook triggered with: {updates}')
            with cond:
                prefetched_data['Run']['status'] = updates['status']
                prefetched_data['log_update'] = updates['log_update']
                logger.info(f"[{updates['status']}] | {updates['log_update']}")

                cond.notify_all()
                logger.debug('all notified')

        client = SimulatorWebSocketClient(
            url=prefetched_data['Run']['ws_status_url'],
            on_update=task_update_signal_hook,
        )
        run_id = prefetched_data['Run']['id']
        client.subscribe(run_id, self.api_key)
        with cond:
            while prefetched_data['Run']['status'] in ['queued', 'running']:
                # block until task update signalled
                cond.wait()
        # closing connection again
        client.close()

    def update_results(self, prefetched_data: dict, keys: list = None, inline: bool = False) -> Optional[dict]:
        """
        Function to (pre)fetch result columns from server and update/append prefetched_data
        """
        # first check if it is a restored incomplete run with an invalid simulator
        if self.api_url is None:
            raise DandeliionAPIException("No valid api_url found in simulator instance. If this is a restored "
                                         "solution, please make sure to provide correct details of the original "
                                         "simulator connection when restoring it.")

        params = [('key', key) for key in keys] if keys is not None else []
        params.append(('id', prefetched_data['Run']['id']))

        headers = {'Authorization': f'Token {self.api_key}'}
        response = requests.get(url=self.api_url, params=params, headers=headers)
        if response.status_code >= 400:
            raise DandeliionAPIException(f"Your request has failed: {get_error_message(response)}. Try again?")

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
                    f"Error code {response.status_code}. Failed to fetch log: {get_error_message(response)}"
                )

        # not buffering log; will change anyway; just return response
        if prefetched_data['Run']['status'] in ['queued', 'running']:
            return response.text

        # store final version of log in buffer if not exists yet
        if 'Log' not in prefetched_data:
            prefetched_data['Log'] = response.text

        return prefetched_data['Log']

    @classmethod
    def restore(cls, filepath: Union[str, Path], api_key=None, api_url=None) -> Solution:
        """
        Loads prefetched/solution data and creates new solution object.
        If api url/key provided (optional), it will also try to connect to server for updates
        for this simulation (e.g. if stored before finished)

        Args:
           filepath (str | Path): path to file were data should be loaded from
           api_key (str, optional): api key used to run this simulation; for default, none is
                                    used and solution won't be able to be updated from server
           api_url (str, optional): url to server where simulation was run; default uses one
                                    stored in file

        Returns:
            Solution: solution instance to access simulation status/results
        """
        # extract api_url from file
        if api_url is None:
            try:
                with open(filepath, 'r') as f:
                    api_url = json.load(f)['Run']['api_url']
            except KeyError:  # no api_url found in file
                pass
        sim = cls(api_url=api_url, api_key=api_key)
        solution = Solution(sim=sim, prefetched_data=filepath, time_column='Time [s]')
        # if key provided, trigger status update to check key (if not finished yet)
        if api_key is not None:
            solution.status
        return solution
