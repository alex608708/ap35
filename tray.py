"""
AP35 Agent — системный трей (pystray + PyQt5)
"""
import os
import sys
import webbrowser
import winreg
import threading

import pystray
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QApplication

import config
import icons
import installer
from heartbeat import HeartbeatThread
from ticket_window import TicketWindow
from updater import UpdaterThread

AUTORUN_NAME = "AP35Agent"
AUTORUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_exe_path() -> str:
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


class _Bridge(QObject):
    """Мост между pystray-потоком и Qt main thread."""
    open_ticket_sig = pyqtSignal()
    quit_sig = pyqtSignal()
    command_sig = pyqtSignal(str, str)  # command, payload


class TrayApp:
    def __init__(self):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        self._bridge = _Bridge()
        self._bridge.open_ticket_sig.connect(self._show_ticket_window)
        self._bridge.quit_sig.connect(self._do_quit)
        self._bridge.command_sig.connect(self._execute_command)

        self._ticket_win: TicketWindow | None = None
        self._status = "pending"

        self._icon = pystray.Icon(
            name="AP35Agent",
            icon=icons.pending(),
            title="AP35 Agent — запуск...",
            menu=self._build_menu(),
        )

        self._hb = HeartbeatThread(self._on_status, self._on_command_received)
        self._hb.start()

        self._updater = UpdaterThread()
        self._updater.start()

        self._ensure_autorun()

    # ── Меню ────────────────────────────────────────────────────────────────

    def _build_menu(self):
        rdid = config.get_rdid()
        if rdid:
            last4 = rdid[-4:]
            id_text = f"ID: ...{last4}"
        else:
            id_text = "ID: не определён"
        return pystray.Menu(
            pystray.MenuItem("AP35 Agent", None, enabled=False),
            pystray.MenuItem(id_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📋 Подать заявку", self._open_ticket, default=True),
            pystray.MenuItem("🌐 Открыть портал",
                             lambda icon, item: webbrowser.open(config.SERVER)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕ Выход", self._quit),
        )

    # ── Heartbeat ───────────────────────────────────────────────────────────

    def _on_status(self, status: str):
        self._status = status
        rdid = config.get_rdid()
        last4 = f" [{rdid[-4:]}]" if rdid else ""
        if status == "online":
            self._icon.icon = icons.online()
            self._icon.title = f"AP35 Agent — онлайн ✔{last4}"
        elif status == "offline":
            self._icon.icon = icons.offline()
            self._icon.title = f"AP35 Agent — нет связи ✗{last4}"
        else:
            self._icon.icon = icons.pending()
            self._icon.title = "AP35 Agent — нет ID"

    # ── Окно заявки ─────────────────────────────────────────────────────────

    def _open_ticket(self, icon=None, item=None):
        # pystray callback — не Qt поток, используем сигнал
        self._bridge.open_ticket_sig.emit()

    def _show_ticket_window(self):
        # Вызывается в Qt main thread
        if self._ticket_win is None:
            self._ticket_win = TicketWindow()
        self._ticket_win.show()
        self._ticket_win.setWindowState(
            self._ticket_win.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
        )
        self._ticket_win.raise_()
        self._ticket_win.activateWindow()

    # ── Команды от сервера ─────────────────────────────────────────────────────

    def _on_command_received(self, command: str, payload: str):
        """Вызывается из heartbeat-потока — передаём в Qt через сигнал"""
        self._bridge.command_sig.emit(command, payload)

    def _execute_command(self, command: str, payload: str):
        """Выполняется в Qt main thread"""
        if command == 'notify':
            self._icon.notify(payload or 'Сообщение от AP35', 'AP35 Agent')
            self._blink_notify(6)
        elif command == 'message':
            dlg = QMessageBox()
            dlg.setWindowTitle('AP35 — Сообщение')
            dlg.setText(payload or 'Сообщение от администратора')
            dlg.setIcon(QMessageBox.Information)
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
            dlg.exec_()
        elif command == 'blink':
            self._blink_icon(6)
        elif command == 'install':
            installer.execute_install(payload)

    def _blink_notify(self, count: int):
        """Мигание иконкой при получении уведомления."""
        import PIL.Image, PIL.ImageDraw, io as _io
        def make_alert():
            img = PIL.Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            d = PIL.ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill=(234, 88, 12, 255))
            d.text((18, 14), '📢', fill='white')
            return img
        try:
            alert_ico = make_alert()
        except Exception:
            alert_ico = icons.pending()
        self._do_blink_notify(alert_ico, count)

    def _do_blink_notify(self, alert_ico, count: int):
        if count <= 0:
            self._icon.icon = icons.online() if self._status == 'online' else icons.offline()
            return
        self._icon.icon = alert_ico
        QTimer.singleShot(500, lambda: self._restore_notify(alert_ico, count))

    def _restore_notify(self, alert_ico, count: int):
        self._icon.icon = icons.online() if self._status == 'online' else icons.offline()
        QTimer.singleShot(500, lambda: self._do_blink_notify(alert_ico, count - 1))

    def _blink_icon(self, count: int):
        if count <= 0:
            self._icon.icon = icons.online() if self._status == 'online' else icons.offline()
            return
        from icons import pending, online, offline
        current = self._icon.icon
        self._icon.icon = pending()
        QTimer.singleShot(400, lambda: self._restore_and_blink(count - 1))

    def _restore_and_blink(self, count: int):
        if self._status == 'online':
            self._icon.icon = icons.online()
        else:
            self._icon.icon = icons.offline()
        QTimer.singleShot(400, lambda: self._blink_icon(count))

    # ── Автостарт ───────────────────────────────────────────────────────────

    def _ensure_autorun(self):
        try:
            exe = _get_exe_path()
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY,
                                 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, AUTORUN_NAME, 0, winreg.REG_SZ, f'"{exe}"')
            winreg.CloseKey(key)
        except Exception:
            pass

    # ── Выход ───────────────────────────────────────────────────────────────

    def _quit(self, icon=None, item=None):
        self._hb.stop()
        self._updater.stop()
        self._icon.stop()
        self._bridge.quit_sig.emit()

    def _do_quit(self):
        self._app.quit()

    # ── Запуск ──────────────────────────────────────────────────────────────

    def run(self):
        # pystray в отдельном потоке
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()
        # Qt event loop в main thread
        self._app.exec_()
