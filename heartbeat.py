"""
Heartbeat — поток отправки статуса на сервер каждые 60 сек
"""
import json
import ssl
import threading
import urllib.request

import config


class HeartbeatThread(threading.Thread):
    def __init__(self, on_status):
        super().__init__(daemon=True)
        self._on_status = on_status   # callback(status: str)
        self._stop_evt = threading.Event()
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE

    def run(self):
        while not self._stop_evt.is_set():
            rdid = config.get_rdid()
            if not rdid:
                self._on_status("no_id")
            else:
                self._on_status("online" if self._send(rdid) else "offline")
            self._stop_evt.wait(config.HEARTBEAT_INTERVAL)

    def _send(self, rdid: str) -> bool:
        try:
            body = json.dumps({"id": rdid}).encode()
            req = urllib.request.Request(
                f"{config.SERVER}/api/heartbeat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10, context=self._ssl)
            return True
        except Exception:
            return False

    def stop(self):
        self._stop_evt.set()
