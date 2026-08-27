"""
AP35 Agent Tray v1.0
"""
import sys
import ctypes

def _already_running() -> bool:
    """Возвращает True если уже запущена другая копия (mutex)."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AP35AgentTray_SingleInstance")
    err = ctypes.windll.kernel32.GetLastError()
    return err == 183  # ERROR_ALREADY_EXISTS

if __name__ == "__main__":
    if _already_running():
        sys.exit(0)
    from tray import TrayApp
    TrayApp().run()
