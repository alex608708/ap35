"""
Heartbeat — поток отправки статуса на сервер каждые 60 сек
Получает и выполняет команды от сервера (notify, message, blink)
"""
import json
import ssl
import threading
import urllib.request

import config


class HeartbeatThread(threading.Thread):
    def __init__(self, on_status, on_command=None):
        super().__init__(daemon=True)
        self._on_status = on_status       # callback(status: str)
        self._on_command = on_command     # callback(command: str, payload: str)
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
                ok, commands = self._send(rdid)
                self._on_status("online" if ok else "offline")
                if commands and self._on_command:
                    for cmd in commands:
                        try:
                            self._on_command(cmd.get('command', ''), cmd.get('payload', ''))
                        except Exception:
                            pass
            self._stop_evt.wait(config.HEARTBEAT_INTERVAL)

    def _send(self, rdid: str):
        try:
            last_cmd_id = int(config.get('last_cmd_id', '0') or 0)
            # workplace.txt (инсталлятор) — приоритет над кэшем при переустановке
            workplace_local = ''
            try:
                from pathlib import Path
                for enc in ('utf-16', 'utf-8', 'cp1251'):
                    try:
                        wp = (config.APP_DIR / 'workplace.txt').read_text(encoding=enc).strip()
                        if wp and len(wp) > 1:
                            workplace_local = wp
                            if wp != config.get('workplace'):
                                config.set_val('workplace', wp)
                            break
                    except Exception:
                        continue
            except Exception:
                pass
            if not workplace_local:
                workplace_local = config.get('workplace', '')
            # Crash log если был
            crash_log = ""
            try:
                from pathlib import Path as _Path
                log_f = _Path(config._CFG_DIR) / "crash.log"
                if log_f.exists() and log_f.stat().st_size > 0:
                    crash_log = log_f.read_text(encoding="utf-8", errors="replace")[-3000:]
                    log_f.write_text("", encoding="utf-8")  # очищаем после отправки
            except Exception:
                pass
            body = json.dumps({"id": rdid, "last_cmd_id": last_cmd_id,
                               "workplace": workplace_local,
                               "crash_log": crash_log}).encode()
            req = urllib.request.Request(
                f"{config.SERVER}/api/heartbeat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10, context=self._ssl) as r:
                data = json.loads(r.read().decode())
            commands = data.get('commands', [])
            if commands:
                max_id = max(c.get('id', 0) for c in commands)
                config.set_val('last_cmd_id', str(max_id))
            # Сохраняем workplace из ответа сервера (всегда актуально)
            workplace = data.get('workplace', '')
            if workplace:
                config.set_val('workplace', workplace)
            return True, commands
        except Exception:
            return False, []

    def stop(self):
        self._stop_evt.set()
