import threading
import json
import websocket
from threading import Condition


class SimulatorWebSocketClient:

    def __init__(self, url: str, api_key: str, on_update=None):

        headers = {'Authorization': f'Token {api_key}'}  # TODO adapt to server

        self._app = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
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
        self._app.send(message)

    def subscribe(self, message):
        with self._is_ready:
            self._is_ready.wait_for(lambda: self._is_opened)
        self.send_message(message)

    def close(self):
        self._app.close()

    def on_open(self, app):
        with self._is_ready:
            self._is_opened = True
            self._is_ready.notify_all()

    def on_update(self, app, message):
        self._on_update(json.loads(message)['updates'])

    def on_close(self, wsapp, close_status_code, close_msg):
        # Because on_close was triggered, we know the opcode = 8
        print("on_close args:")
        print("close status code: " + str(close_status_code))
        print("close message: " + str(close_msg))

    def on_error(self, app, err):
        print("ERROR", app, err)
