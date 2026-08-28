"""
AP35 Agent Tray — настройки
"""
import os
import configparser
from pathlib import Path

# EXE и rdid.txt — в Program Files (читаем только, пишет installer как admin)
# ProgramW6432 всегда указывает на 64-бит Program Files (даже из 32-бит процесса)
APP_DIR = Path(
    os.environ.get("ProgramW6432") or
    os.environ.get("ProgramFiles") or
    "C:/Program Files"
) / "AP35Agent"
RDID_FILE = APP_DIR / "rdid.txt"

# Конфиг — в APPDATA (всегда доступен на запись текущему пользователю)
_CFG_DIR = Path(os.environ.get("APPDATA", "C:/Users/Public/AppData/Roaming")) / "AP35Agent"
CONFIG_FILE = _CFG_DIR / "agent_tray.ini"

SERVER = "https://help.ap35.ru:5000"
TOKEN = "AP35AgentReg2026"
HEARTBEAT_INTERVAL = 60  # секунд

_cfg = configparser.ConfigParser()


def _load():
    if CONFIG_FILE.exists():
        _cfg.read(CONFIG_FILE, encoding="utf-8")
    if "app" not in _cfg:
        _cfg["app"] = {}


def get_rdid() -> str:
    """Читает rdid из Program Files. Если пусто — генерирует из Machine GUID."""
    try:
        v = RDID_FILE.read_text(encoding="utf-8").strip()
        if v:
            return v
    except Exception:
        pass
    # Fallback: стабильный ID из Machine GUID Windows
    _fallback = _CFG_DIR / "rdid.txt"
    try:
        if _fallback.exists():
            v = _fallback.read_text(encoding="utf-8").strip()
            if v:
                return v
    except Exception:
        pass
    try:
        import winreg, hashlib
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        h = hashlib.md5(guid.encode()).hexdigest()
        machine_id = str(int(h[:8], 16) % 900000000 + 100000000)  # 9 цифр
        _CFG_DIR.mkdir(parents=True, exist_ok=True)
        _fallback.write_text(machine_id, encoding="utf-8")
        return machine_id
    except Exception:
        return ""


def get(key: str, fallback: str = "") -> str:
    _load()
    return _cfg.get("app", key, fallback=fallback)


def set_val(key: str, value: str):
    _load()
    _cfg["app"][key] = value
    try:
        _CFG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            _cfg.write(f)
    except Exception:
        pass  # Не критично — значение уже в памяти
