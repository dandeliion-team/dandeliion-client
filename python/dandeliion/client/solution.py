"""
@file python/dandeliion/client/solution.py

Module containing class for handling access to solutions
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
import copy
from typing import Protocol, Optional

# custom modules
from .exceptions import DandeliionAPIException

logger = logging.getLogger(__name__)


class Simulator(Protocol):
    """ Simulator Protocol """
    def update_results(self, prefetched_data: dict, keys: list = None, inline: bool = False) -> Optional[dict]: ...
    def get_status(self, prefetched_data: dict) -> str: ...


class Solution:
    """Dictionary-style class for the solutions of a simulation run
    returned by :meth:`solve`
    """

    _data: dict = None
    _sim: Simulator = None

    def __init__(self, sim: Simulator, prefetched_data: dict):
        """
        Constructor

        Args:
            sim (Simulator): simulator instance for fetching data from server
            prefetched_data (dict): existing (meta) data
        """
        self._sim = sim
        self._data = prefetched_data

    def __getitem__(self, key: str):
        """Returns the results requested by the key.

        Args:
            key (str): key for results to be returned.

        Returns:
            object: data as requested by provided key
        """

        # if solution not initialised yet, try to fetch from server
        if self._data.get('Solution', None) is None:
            self._sim.update_results(self._data, inline=True)
            # if solution still not initialised (e.g. because simulation
            # failed or has not finished yet), raise Exception
            if self._data['Solution'] is None:
                raise DandeliionAPIException(
                    'Solution not ready (yet). Check status for details.'
                )

        if key not in self._data['Solution']:
            raise KeyError(
                f'Column for {key} does not exist in solution.'
            )
        # fetch data if necessary
        if self._data['Solution'][key] is None:
            self._sim.update_results(self._data, keys=[key], inline=True)
        return copy.deepcopy(self._data['Solution'][key])

    @property
    def status(self):
        return self._sim.get_status(self._data)

    def __setitem__(self, key: str, value):
        raise NotImplementedError("This is a read-only dictionary")

    def __len__(self):
        return len(self.keys())

    def __delitem__(self, key):
        raise NotImplementedError("This is a read-only dictionary")

    def clear(self):
        raise NotImplementedError("This is a read-only dictionary")

    def copy(self):
        return self  # nothing to do since read-only anyways

    def has_key(self, k):
        return k in self.keys()

    def update(self, *args, **kwargs):
        raise NotImplementedError("This is a read-only dictionary")

    def keys(self):
        return self._results['Solution'].keys()

    def values(self):
        return self._results['Solution'].values()

    def items(self):
        return self._data['Solution'].items()

    def pop(self, *args):
        raise NotImplementedError("This is a read-only dictionary")

    def __contains__(self, item):
        return item in self.items()

    def __iter__(self):
        for key in self.keys():
            yield key
