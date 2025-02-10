# built-in modules
import logging
import requests
import threading

# custom modules
from .websocket import SimulatorWebSocketClient
from .exceptions import DandeliionAPIException

logger = logging.getLogger(__name___)


@dataclass
class Simulator:

    """
    Simulator class that stores authentication details and deals with job submission
    """
    
    api_url: str
    api_key: str
    
    def submit(self, parameters: dict, is_blocking: bool):
        # submit simulation to rest api
        headers = {'Authorization': f'Token {api_key}'}  # TODO adapt to server
        response = requests.post(api_url, json=parameters, headers=headers)
        if response.status_code >= 400:
            raise DandeliionAPIException(f"Your request has failed: {response.reason}")
        response_json = response.json()
        if is_blocking:
            cond = threading.Condition()

            def task_update_signal_hook(updates):
                response_json['status'] = updates['status']
                logger.info(updates['log_message'])
                cond.notify_all()
                
            client = SimulationWebSocketClient(
                url=response_json['ws_status_url'],
                api_key=api_key,
                on_update=task_update_signal_hook,
            )
            client.subscribe(response_json['id'])
            while response_json.status in ['Q', 'R']:
                # block until task update signalled
                with cond:
                    cond.wait()
                else:
                    break
            # closing connection again
            client.close()

        return Solution(response_json)
