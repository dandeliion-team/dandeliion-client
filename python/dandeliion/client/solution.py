# built-in modules
import logging
import requests

# custom modules
from .exceptions import DandeliionAPIException

logger = logging.getLogger(__name___)


class Solution:
    """Dictionary-style class for the solutions of a simulation run
    returned by :meth:`solve`. Currently contains:

            * 'Time [s]'
            * 'Voltage [V]'
            * 'Current [A]'
    """

    valid_keys = {
        "Time [s]": ("total_voltage", "t(s)"),
        "Voltage [V]": ("total_voltage", "total_voltage(V)"),
        "Current [A]": ("total_current", "total_current(A)"),
    }

    _results = None

    def __init__(self, config: dict):
        """
        Args:
            config (dict): dictionary should contain url to fetch data and authentication credentials
        """
        self._config = config
    
    def __str__(self):
        return f"Solution(run {str(self._config.id)})"

    def __getitem__(self, key: str):
        """Returns the results requested by the key.

        Args:
            key (str): key for results to be returned.

        Returns:
            object: data as requested by provided key
        """

        # fetch all results if necessary  # TODO fetch for each item separately
        if not self._results:
            headers = {'Authorization': f'Token {api_key}'}  # TODO adapt to server
            response = requests.get(self._config['results_url'], headers)
            if response.status_code >= 400:
                raise DandeliionAPIException(f"Your request has failed: {response.reason}")
            self._logs = response.json()['logs']
            self._results = response.json()['results']
        
        if key in self.valid_keys:
            return getattr(self._results, self.valid_keys[key][0])[self.valid_keys[key][1]]
        else:
            raise KeyError(f'The following key is not (yet) found in the provided results: {key}')

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
        return self.valid_keys.keys()

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

    @property
    def stop_message(self):
        """
        stop message for simulation run linked to this solution
        """
        return self._sim.stop_message
