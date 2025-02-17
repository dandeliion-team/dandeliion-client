"""
@file python/dandeliion/client/solution.py

Module containing class for handling fetching of/access to solutions
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
import copy

# custom modules
from .exceptions import DandeliionAPIException

logger = logging.getLogger(__name__)


class Solution:
    """Dictionary-style class for the solutions of a simulation run
    returned by :meth:`solve`
    """

    _results = None

    def __init__(self, config: dict):
        """
        Constructor

        Args:
            config (dict): dictionary should contain url to fetch data and authentication credentials as well as simulation id and list of expected data columns in results
        """
        self._config = config
        self._results = {'Solution': {}}

    def __str__(self):
        return f"Solution(run {str(self._config.id)})"

    def fetch_results(self, keys: list = None, force_refetch: bool = False):
        """
        Function to (pre)fetch data columns from results server if necessary
        """
        # determine which keys need to be fetched
        if keys is None:
            keys = self.keys()

        params = [('key', key) for key in keys if self._results['Solution'][key] is None or force_refetch]
        # if no keys need to be fetched, nothing to do
        if not params:
            return
        params.append(('id', self._config['id']))
        
        headers = {'Authorization': f"Token {self._config['api_key']}"}  # TODO adapt to server
        response = requests.get(url=self._config['results_url'], params=params, headers=headers)
        if response.status_code >= 400:
            raise DandeliionAPIException(f"Your request has failed: {response.reason}")
        update_dict(self._results, response.json, inline=True)

    def __getitem__(self, key: str):
        """Returns the results requested by the key.

        Args:
            key (str): key for results to be returned.

        Returns:
            object: data as requested by provided key
        """

        if 'columns' in self._config and key not in self._config['c']:
            raise KeyError(
                f'Column for {key} does not exist in solution. Perhaps '
                'simulation has not finished successfully (yet)?'
            )
        # fetch results for missing key
        self.fetch_results(keys=[key])
        return copy.deepcopy(self._results['Solution'][key])

    def __setitem__(self, key: str, value):
        raise NotImplementedError("This is a read-only dictionary")

    def __len__(self):
        return len(self.valid_keys)

    def __delitem__(self, key):
        raise NotImplementedError("This is a read-only dictionary")

    def clear(self):
        raise NotImplementedError("This is a read-only dictionary")

    def copy(self):
        return self  # nothing to do since read-only anyways

    def has_key(self, k):
        return k in self.valid_keys

    def update(self, *args, **kwargs):
        raise NotImplementedError("This is a read-only dictionary")

    def keys(self):
        if 'result_columns' in self._config:
            return self._config['result_columns']
        else:
            return self._results['Solution'].keys()

    def values(self):
        return [getattr(self._sim.results, val[0])[val[1]] for key, val in self.valid_keys.items()]

    def items(self):
        # a bit dirty, but since solution is read-only, it works
        return {key: getattr(self._sim.results, val[0])[val[1]] for key, val in self.valid_keys.items()}.items()

    def pop(self, *args):
        raise NotImplementedError("This is a read-only dictionary")

    def __contains__(self, item):
        return item in self.items()

    def __iter__(self):
        for key in self.valid_keys:
            yield key
