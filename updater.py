"""
AP35 Agent Tray — авто-обновление
Проверяет версию на сервере каждые 4 часа.
Если версия отличается — скачивает новый EXE и перезапускает агент через .bat.
"""
import json
import os
import ssl
import subprocess
import tempfile
import threading
import urllib.request

import config

CHECK_INTERVAL   = 4 * 3600   # проверка каждые 4 часа
FIRST_CHECK_DELAY = 5 * 60    # первая проверка через 5 минут после старта


class UpdaterThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_evt = threading.Event()
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE

    # ── Внутренние методы ─────────────────────────────────────────────────

    def _get_local_version(self) -> str:
        ver_file = config.APP_DIR / "version.txt"
        try:
            return ver_file.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _get_server_version(self) -> str:
        req = urllib.request.Request(
            f"{config.SERVER}/api/agent_version",
            headers={"User-Agent": "AP35AgentTray/updater"}
        )
        with urllib.request.urlopen(req, timeout=10, context=self._ssl) as r:
            data = json.loads(r.read())
        return str(data.get("version", "")).strip()

    def _download(self, url: str, dest: str):
        req = urllib.request.Request(url, headers={"User-Agent": "AP35AgentTray/updater"})
        with urllib.request.urlopen(req, timeout=120, context=self._ssl) as r, \
             open(dest, "wb") as f:
            f.write(r.read())

    def _check(self):
        local_ver  = self._get_local_version()
        server_ver = self._get_server_version()

        if not server_ver or server_ver == local_ver:
            return   # уже актуальная версия

        # Скачиваем новый EXE во временную папку
        tmp_dir  = tempfile.gettempdir()
        new_exe  = os.path.join(tmp_dir, "AP35AgentTray_new.exe")
        bat_path = os.path.join(tmp_dir, "ap35_update.bat")

        self._download(f"{config.SERVER}/download/agent_tray", new_exe)

        if not os.path.exists(new_exe) or os.path.getsize(new_exe) < 100_000:
            return   # скачался пустой или битый файл

        # Пишем version.txt через bat (чтобы записалась уже после успешной замены EXE)
        bat_lines = [
            "@echo off",
            "timeout /t 2 /nobreak >nul",
            f'copy /y "{new_exe}" "C:\\AP35Agent\\AP35AgentTray.exe"',
            f'echo {server_ver}> "C:\\AP35Agent\\version.txt"',
            'start "" "C:\\AP35Agent\\AP35AgentTray.exe"',
            f'del "{new_exe}"',
            'del "%~f0"',
        ]
        with open(bat_path, "w", encoding="cp866") as f:
            f.write("\r\n".join(bat_lines))

        # Запускаем bat скрыто и выходим — он подождёт и заменит нас
        subprocess.Popen(
            ["cmd", "/c", "start", "", "/min", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True
        )
        self._stop_evt.wait(2)
        os._exit(0)

    # ── Основной цикл ─────────────────────────────────────────────────────

    def run(self):
        self._stop_evt.wait(FIRST_CHECK_DELAY)
        while not self._stop_evt.is_set():
            try:
                self._check()
            except Exception:
                pass
            self._stop_evt.wait(CHECK_INTERVAL)

    def stop(self):
        self._stop_evt.set()
