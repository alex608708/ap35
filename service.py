"""
AP35 Heartbeat — Windows Service
Устанавливается: AP35AgentService.exe install
Запускается:     net start AP35Agent
Виден в services.msc как "AP35 Agent Heartbeat"
Включает watchdog: перезапускает AP35AgentTray.exe если он упал.
"""
import os
import sys
import time
import subprocess
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil

import config
from heartbeat import HeartbeatThread

TRAY_EXE = os.path.join(os.path.dirname(sys.executable), "AP35AgentTray.exe")
WATCHDOG_INTERVAL = 60  # секунд


def _is_tray_running() -> bool:
    """Проверить, запущен ли AP35AgentTray.exe."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq AP35AgentTray.exe", "/NH"],
            stderr=subprocess.DEVNULL, timeout=10
        ).decode(errors="ignore")
        return "AP35AgentTray.exe" in out
    except Exception:
        return False


def _start_tray_in_user_session():
    """Запускает AP35AgentTray.exe в сессии активного пользователя через schtasks."""
    if not os.path.exists(TRAY_EXE):
        return
    try:
        # Создаём временную задачу от имени текущего пользователя сессии
        subprocess.run([
            "schtasks", "/create", "/f",
            "/tn", "AP35TrayRestart",
            "/tr", f'"{TRAY_EXE}"',
            "/sc", "once",
            "/st", "00:00",
            "/ru", "INTERACTIVE",   # текущий интерактивный пользователь
            "/rl", "LIMITED"
        ], timeout=10, capture_output=True)
        subprocess.run(["schtasks", "/run", "/tn", "AP35TrayRestart"],
                       timeout=5, capture_output=True)
        time.sleep(3)
        subprocess.run(["schtasks", "/delete", "/tn", "AP35TrayRestart", "/f"],
                       timeout=5, capture_output=True)
    except Exception as e:
        servicemanager.LogWarningMsg(f"AP35 watchdog: не удалось запустить трей: {e}")


class TrayWatchdog(threading.Thread):
    """Следит за трей-приложением, перезапускает при необходимости."""
    def __init__(self, stop_evt):
        super().__init__(daemon=True)
        self._stop = stop_evt

    def run(self):
        # Пауза при старте — дать время на вход пользователя
        self._stop.wait(30)
        while not self._stop.is_set():
            try:
                if not _is_tray_running() and os.path.exists(TRAY_EXE):
                    servicemanager.LogInfoMsg("AP35 watchdog: трей не найден, перезапуск...")
                    _start_tray_in_user_session()
            except Exception as e:
                servicemanager.LogWarningMsg(f"AP35 watchdog error: {e}")
            self._stop.wait(WATCHDOG_INTERVAL)


class AP35Service(win32serviceutil.ServiceFramework):
    _svc_name_         = "AP35Agent"
    _svc_display_name_ = "AP35 Agent Heartbeat"
    _svc_description_  = "Мониторинг и heartbeat агента AP35 (Алекс-Профи)"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._stop_evt = win32event.CreateEvent(None, 0, 0, None)
        self._stop_flag = threading.Event()
        self._hb = None
        self._watchdog = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._hb:
            self._hb.stop()
        self._stop_flag.set()
        win32event.SetEvent(self._stop_evt)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("AP35 Agent Heartbeat: запуск")
        self._hb = HeartbeatThread(on_status=self._on_status)
        self._hb.start()
        self._watchdog = TrayWatchdog(self._stop_flag)
        self._watchdog.start()
        win32event.WaitForSingleObject(self._stop_evt, win32event.INFINITE)
        servicemanager.LogInfoMsg("AP35 Agent Heartbeat: остановка")

    def _on_status(self, status: str):
        pass


def main():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AP35Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AP35Service)


if __name__ == '__main__':
    main()
