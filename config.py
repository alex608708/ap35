"""
AP35 Agent Tray — настройки
"""
import os
import configparser
from pathlib import Path

APP_DIR = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "AP35Agent"
RDID_FILE = APP_DIR / "rdid.txt"
CONFIG_FILE = APP_DIR / "agent_tray.ini"

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
    try:
        return RDID_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def get(key: str, fallback: str = "") -> str:
    _load()
    return _cfg.get("app", key, fallback=fallback)


def set_val(key: str, value: str):
    _load()
    _cfg["app"][key] = value
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        _cfg.write(f)
