"""
Окно подачи заявки — PyQt5
"""
import json
import os
import re
import ssl
import subprocess
import threading
import urllib.request
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPalette, QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QFrame, QSizePolicy,
    QScrollArea
)

import config

# ── Цвета ────────────────────────────────────────────────────────────────────
BG       = "#0f172a"
BG2      = "#1e293b"
BG_ORG   = "#1a2744"
BORDER   = "#334155"
FG       = "#e2e8f0"
FG_DIM   = "#64748b"
ACCENT   = "#6c63ff"
GREEN    = "#86efac"
RED      = "#fca5a5"
YELLOW   = "#fbbf24"


def _css_entry():
    return f"""
        QLineEdit, QTextEdit {{
            background: {BG2};
            color: {FG};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 6px 8px;
            font-size: 13px;
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {ACCENT};
        }}
        QLineEdit:read-only {{
            color: {FG_DIM};
        }}
    """


def _detect_domain():
    computer   = os.environ.get('COMPUTERNAME', '').upper()
    userdomain = os.environ.get('USERDOMAIN', '').upper()
    if not userdomain or userdomain == computer:
        return False, ''
    username = os.environ.get('USERNAME', '')
    fio = ''
    try:
        result = subprocess.run(['net', 'user', username, '/domain'],
                                capture_output=True, timeout=8)
        for enc in ('cp866', 'cp1251', 'utf-8'):
            try:
                text = result.stdout.decode(enc)
                for line in text.split('\n'):
                    m = re.match(r'^(?:Full Name|Полное имя)\s+(.*)', line.strip(), re.IGNORECASE)
                    if m:
                        fio = m.group(1).strip()
                        break
                if fio:
                    break
            except Exception:
                continue
    except Exception:
        pass
    return True, fio


def _read_workplace() -> str:
    """Читаем workplace из нового или старого пути (обратная совместимость)."""
    for base in [config.APP_DIR, Path("C:/AP35Agent")]:
        txt = base / "workplace.txt"
        if txt.exists():
            try:
                v = txt.read_text(encoding='utf-8').strip()
                if v:
                    return v
            except Exception:
                pass
    return config.get("workplace")


class HistoryThread(QThread):
    """Загружает историю заявок от этого агента."""
    done = pyqtSignal(list)

    def run(self):
        rdid = config.get_rdid()
        if not rdid:
            self.done.emit([])
            return
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(
                f"{config.SERVER}/api/tickets?token={config.TOKEN}&rdid={rdid}",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as r:
                data = json.loads(r.read().decode('utf-8'))
            self.done.emit(data.get('tickets', []))
        except Exception:
            self.done.emit([])


class TicketWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Новая заявка — AP35")
        self.setFixedWidth(440)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(f"QWidget {{ background: {BG}; color: {FG}; font-family: 'Segoe UI'; }}")

        self._is_domain, self._domain_fio = _detect_domain()
        self._workplace = _read_workplace()
        self._history_visible = False

        self._build()
        self._center()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Панель истории (слева, скрыта) ───────────────────────────────────
        self._history_panel = QFrame()
        self._history_panel.setFixedWidth(0)
        self._history_panel.setStyleSheet(f"QFrame {{ background: {BG2}; border-right: 1px solid {BORDER}; }}")
        hist_layout = QVBoxLayout(self._history_panel)
        hist_layout.setContentsMargins(12, 16, 12, 12)
        hist_layout.setSpacing(6)

        hist_title = QLabel("📋 Мои заявки")
        hist_title.setStyleSheet(f"color:{FG}; font-size:13px; font-weight:700;")
        hist_layout.addWidget(hist_title)

        self._hist_scroll = QScrollArea()
        self._hist_scroll.setWidgetResizable(True)
        self._hist_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG2}; }}")
        self._hist_content = QLabel("Загрузка...")
        self._hist_content.setWordWrap(True)
        self._hist_content.setAlignment(Qt.AlignTop)
        self._hist_content.setStyleSheet(f"color:{FG_DIM}; font-size:11px; padding:4px;")
        self._hist_scroll.setWidget(self._hist_content)
        hist_layout.addWidget(self._hist_scroll)

        root.addWidget(self._history_panel)

        # ── Основной контент ─────────────────────────────────────────────────
        main_frame = QFrame()
        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Бейдж ID агента
        rdid = config.get_rdid()
        id_frame = QFrame()
        id_frame.setStyleSheet("QFrame { background:#052e16; border:1px solid #4ade80; border-radius:6px; }")
        id_row = QHBoxLayout(id_frame)
        id_row.setContentsMargins(12, 6, 12, 6)
        id_row.setSpacing(0)

        if rdid:
            last4  = rdid[-4:]
            prefix = rdid[:-4] if len(rdid) > 4 else ""
            id_html = (
                f'<span style="color:#86efac;font-size:11px;">ID:&nbsp;</span>'
                f'<span style="color:#94a3b8;font-size:11px;">{prefix}</span>'
                f'<span style="color:#4ade80;font-size:18px;font-weight:800;">{last4}</span>'
            )
        else:
            id_html = '<span style="color:#94a3b8;font-size:11px;">ID: не определён</span>'

        id_lbl = QLabel(id_html)
        id_lbl.setTextFormat(Qt.RichText)
        id_lbl.setStyleSheet("background:transparent; border:none;")
        id_row.addWidget(id_lbl)
        id_row.addStretch()

        # Кнопка История
        btn_hist = QPushButton("📋 История")
        btn_hist.setStyleSheet(f"""
            QPushButton {{
                background:#1e293b; color:{FG_DIM};
                border:1px solid {BORDER}; border-radius:4px;
                padding:3px 10px; font-size:11px;
            }}
            QPushButton:hover {{ background:#283548; color:{FG}; }}
        """)
        btn_hist.clicked.connect(self._toggle_history)
        id_row.addWidget(btn_hist)
        layout.addWidget(id_frame)

        # Заголовок
        title = QLabel("📋  Новая заявка")
        title.setStyleSheet(f"color:{FG}; font-size:17px; font-weight:700; margin-top:4px;")
        layout.addWidget(title)

        # Организация
        org_frame = QFrame()
        org_frame.setStyleSheet(f"""
            QFrame {{
                background: {BG_ORG};
                border: 1px solid {ACCENT};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        org_layout = QVBoxLayout(org_frame)
        org_layout.setContentsMargins(12, 8, 12, 10)
        org_layout.setSpacing(2)

        org_lbl = QLabel("ОРГАНИЗАЦИЯ")
        org_lbl.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-weight:600; border:none;")
        org_layout.addWidget(org_lbl)

        org_val = self._workplace if self._workplace else "не задана"
        org_name = QLabel(f"🏢  {org_val}")
        org_name.setStyleSheet(f"color:{FG}; font-size:14px; font-weight:600; border:none;")
        org_layout.addWidget(org_name)
        layout.addWidget(org_frame)

        layout.addSpacing(4)
        layout.addWidget(self._sep())

        # Тема *
        layout.addWidget(self._cap("ТЕМА ЗАЯВКИ *"))
        self.inp_subject = QLineEdit()
        self.inp_subject.setStyleSheet(_css_entry())
        self.inp_subject.setPlaceholderText("Кратко опишите проблему...")
        layout.addWidget(self.inp_subject)

        # Описание
        layout.addWidget(self._cap("ОПИСАНИЕ"))
        self.inp_content = QTextEdit()
        self.inp_content.setStyleSheet(_css_entry())
        self.inp_content.setFixedHeight(70)
        self.inp_content.setPlaceholderText("Подробности (необязательно)...")
        layout.addWidget(self.inp_content)

        # ФИО
        if self._is_domain and self._domain_fio:
            fio_cap = "ВАШЕ ФИО (из домена)"
        elif self._is_domain:
            fio_cap = "ВАШЕ ФИО (домен, имя не найдено)"
        else:
            fio_cap = "ВАШЕ ФИО *"
        layout.addWidget(self._cap(fio_cap))
        self.inp_fio = QLineEdit()
        self.inp_fio.setStyleSheet(_css_entry())
        fio_val = self._domain_fio or config.get("fio")
        if fio_val:
            self.inp_fio.setText(fio_val)
        if self._is_domain and self._domain_fio:
            self.inp_fio.setReadOnly(True)
        layout.addWidget(self.inp_fio)

        # Телефон *
        layout.addWidget(self._cap("ТЕЛЕФОН ДЛЯ СВЯЗИ *"))
        self.inp_phone = QLineEdit()
        self.inp_phone.setStyleSheet(_css_entry())
        self.inp_phone.setText(config.get("phone"))
        self.inp_phone.setPlaceholderText("+7 (999) 000-00-00")
        layout.addWidget(self.inp_phone)

        layout.addWidget(self._sep())

        # Статус
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet(f"color:{GREEN}; font-size:12px;")
        layout.addWidget(self.lbl_status)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background:{BG2}; color:{FG_DIM};
                border:none; border-radius:6px; padding:8px 16px; font-size:13px;
            }}
            QPushButton:hover {{ background:#283548; }}
        """)
        btn_cancel.clicked.connect(self.hide)

        self.btn_send = QPushButton("📨  Отправить")
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:white;
                border:none; border-radius:6px; padding:8px 20px;
                font-size:13px; font-weight:600;
            }}
            QPushButton:hover {{ background:#5a52d5; }}
            QPushButton:disabled {{ background:#334155; color:{FG_DIM}; }}
        """)
        self.btn_send.clicked.connect(self._submit)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_send)
        layout.addLayout(btn_row)

        root.addWidget(main_frame)
        self.inp_subject.setFocus()

    def _cap(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-weight:600;")
        return lbl

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{BORDER};")
        return line

    def _center(self):
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            margin = 16
            self.move(
                screen.right() - self.width() - margin,
                screen.bottom() - self.height() - margin
            )
        except Exception:
            pass

    # ── История ──────────────────────────────────────────────────────────────

    def _toggle_history(self):
        self._history_visible = not self._history_visible
        target_w = 220 if self._history_visible else 0

        self._anim = QPropertyAnimation(self._history_panel, b"minimumWidth")
        self._anim.setDuration(200)
        self._anim.setStartValue(self._history_panel.width())
        self._anim.setEndValue(target_w)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

        self._anim2 = QPropertyAnimation(self._history_panel, b"maximumWidth")
        self._anim2.setDuration(200)
        self._anim2.setStartValue(self._history_panel.width())
        self._anim2.setEndValue(target_w)
        self._anim2.setEasingCurve(QEasingCurve.OutCubic)
        self._anim2.start()

        if self._history_visible:
            self._load_history()

    def _load_history(self):
        self._hist_content.setText("Загрузка...")
        t = HistoryThread(self)
        t.done.connect(self._show_history)
        t.start()

    def _show_history(self, tickets: list):
        if not tickets:
            self._hist_content.setText("Заявок пока нет")
            return

        STATUS_COLOR = {
            'new': YELLOW, 'open': '#60a5fa', 'closed': GREEN,
            'resolved': GREEN, 'pending': FG_DIM,
        }
        STATUS_LABEL = {
            'new': '🆕 Новая', 'open': '🔄 В работе',
            'closed': '✅ Закрыта', 'resolved': '✅ Решена',
            'pending': '⏳ Ожидание',
        }
        lines = []
        for t in tickets[:20]:
            tid    = t.get('id', '?')
            subj   = t.get('subject', '')[:30]
            status = t.get('status', 'new')
            date   = str(t.get('date', ''))[:10]
            color  = STATUS_COLOR.get(status, FG_DIM)
            slabel = STATUS_LABEL.get(status, status)
            lines.append(
                f'<div style="border-bottom:1px solid #1e293b;padding:6px 0;">'
                f'<span style="color:{FG_DIM};font-size:10px;">№{tid} · {date}</span><br>'
                f'<span style="color:{FG};font-size:11px;">{subj}</span><br>'
                f'<span style="color:{color};font-size:10px;">{slabel}</span>'
                f'</div>'
            )
        self._hist_content.setTextFormat(Qt.RichText)
        self._hist_content.setText(''.join(lines))

    # ── Отправка ─────────────────────────────────────────────────────────────

    def _submit(self):
        subject = self.inp_subject.text().strip()
        if not subject:
            self._set_status("Укажите тему заявки", error=True)
            return
        fio = self.inp_fio.text().strip()
        if not self._is_domain and not fio:
            self._set_status("Укажите ваше ФИО", error=True)
            return
        phone = self.inp_phone.text().strip()
        if not phone:
            self._set_status("Укажите телефон для связи", error=True)
            return
        workplace = self._workplace
        if not workplace:
            self._set_status("Организация не задана. Обратитесь к администратору.", error=True)
            return

        if fio and not (self._is_domain and self._domain_fio):
            config.set_val("fio", fio)
        config.set_val("phone", phone)

        payload = {
            "token": config.TOKEN,
            "rustdesk_id": config.get_rdid(),
            "subject": subject,
            "content": self.inp_content.toPlainText().strip(),
            "fio": fio,
            "phone": phone,
            "workplace": workplace,
        }

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Отправка...")
        self._set_status("", error=False)
        threading.Thread(target=self._do_send, args=(payload,), daemon=True).start()

    def _do_send(self, payload):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(
                f"{config.SERVER}/api/ticket",
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
                data = json.loads(r.read().decode('utf-8'))
            if data.get("ok"):
                self._qt_call(self._on_ok, f"✅  Заявка №{data.get('ticket_id','?')} создана!")
            else:
                self._qt_call(self._on_err, data.get("error", "Ошибка сервера"))
        except Exception as e:
            self._qt_call(self._on_err, f"Ошибка соединения: {e}")

    def _qt_call(self, fn, *args):
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: fn(*args))

    def _on_ok(self, msg):
        self._set_status(msg, error=False)
        self.btn_send.setEnabled(True)
        self.btn_send.setText("📨  Отправить")
        self.inp_subject.clear()
        self.inp_content.clear()
        # Обновить историю если открыта
        if self._history_visible:
            QTimer.singleShot(1000, self._load_history)

    def _on_err(self, msg):
        self._set_status(f"❌  {msg}", error=True)
        self.btn_send.setEnabled(True)
        self.btn_send.setText("📨  Отправить")

    def _set_status(self, text, error=False):
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"color:{RED if error else GREEN}; font-size:12px;")
