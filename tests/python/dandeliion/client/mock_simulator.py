"""
@file python/dandeliion/client/mock_simulator.py

module containing Dandeliion MockSimulator class
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
import copy
from typing import Optional
from pathlib import Path
import logging

# custom modules
from dandeliion.client import Solution, Simulator
from dandeliion.client.tools.misc import update_dict

with open(Path(__file__).parent / 'data' / 'output_server_submit.json', 'r') as f:
    submit_data = json.load(f)
with open(Path(__file__).parent / 'data' / 'output_server_finished.json', 'r') as f:
    fetch_data = json.load(f)


logger = logging.getLogger(__name__)


class MockSimulator(Simulator):

    def submit(self, parameters: dict, is_blocking: bool = True):
        if isinstance(self.api_url, Path):
            with open(self.api_url, 'w') as f:
                json.dump(parameters, f, indent=4)
                logger.info(f"Submitted parameters written to file: {self.api_url}")
        return Solution(self, copy.deepcopy(submit_data), time_column='Time [s]')

    def update_results(self, prefetched_data: dict, keys: list = None, inline: bool = False) -> Optional[dict]:
        fetched_data = copy.deepcopy(fetch_data)
        if keys is None:
            fetched_data['Solution'] = {key: None for key in fetched_data['Solution'].keys()}
        else:
            fetched_data['Solution'] = {key: value for key, value in fetched_data['Solution'].items() if key in keys}
        if inline:
            update_dict(prefetched_data, fetched_data)
        else:
            return fetched_data
