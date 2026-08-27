"""
AP35 Agent Tray v1.0
"""
import sys
import ctypes
import traceback
import os
from pathlib import Path


def _already_running() -> bool:
    """Возвращает True если уже запущена другая копия (mutex)."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AP35AgentTray_SingleInstance")
    err = ctypes.windll.kernel32.GetLastError()
    return err == 183  # ERROR_ALREADY_EXISTS


def _crash_log(exc_type, exc_val, exc_tb):
    """Записывает неперехваченные исключения в лог-файл."""
    log_dir = Path(os.environ.get("APPDATA", "C:/Users/Public/AppData/Roaming")) / "AP35Agent"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "crash.log", "a", encoding="utf-8") as f:
            import datetime
            f.write(f"\n=== {datetime.datetime.now()} ===\n")
            f.write("".join(traceback.format_exception(exc_type, exc_val, exc_tb)))
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_val, exc_tb)


if __name__ == "__main__":
    sys.excepthook = _crash_log
    if _already_running():
        sys.exit(0)
    from tray import TrayApp
    TrayApp().run()
