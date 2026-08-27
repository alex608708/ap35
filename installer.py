"""
Удалённая установка приложений от имени SYSTEM через schtasks
"""
import json
import os
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.request

import config


def _report(app_id, app_name, status, detail=''):
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        body = json.dumps({
            'token': config.TOKEN,
            'rustdesk_id': config.get_rdid(),
            'app_id': app_id,
            'app_name': app_name,
            'status': status,
            'detail': str(detail)[:500],
        }, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            f"{config.SERVER}/api/install_result",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
    except Exception:
        pass


def _download(url: str, dest: str) -> bool:
    """Скачать файл с HTTP/HTTPS, игнорируя SSL."""
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, timeout=120, context=ssl_ctx) as r:
            with open(dest, 'wb') as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception:
        return False


def _run_as_system(cmd: str, task_name: str) -> tuple:
    """Запустить команду через schtasks от SYSTEM. Вернуть (ok, detail)."""
    try:
        subprocess.run(
            ['schtasks', '/delete', '/tn', task_name, '/f'],
            capture_output=True
        )
        r = subprocess.run(
            ['schtasks', '/create', '/tn', task_name,
             '/tr', cmd, '/sc', 'ONCE', '/st', '00:00',
             '/ru', 'SYSTEM', '/rl', 'HIGHEST', '/f'],
            capture_output=True, text=True, encoding='cp866', errors='replace'
        )
        if r.returncode != 0:
            return False, r.stderr or r.stdout

        subprocess.run(['schtasks', '/run', '/tn', task_name], capture_output=True)
        # Ждём завершения задачи (до 5 минут)
        for _ in range(60):
            time.sleep(5)
            st = subprocess.run(
                ['schtasks', '/query', '/tn', task_name, '/fo', 'CSV', '/nh'],
                capture_output=True, text=True, encoding='cp866', errors='replace'
            )
            if 'Running' not in (st.stdout or ''):
                break
        subprocess.run(
            ['schtasks', '/delete', '/tn', task_name, '/f'],
            capture_output=True
        )
        return True, 'OK'
    except Exception as e:
        return False, str(e)


def execute_install(payload_str: str):
    """Выполнить установку в фоновом потоке."""
    threading.Thread(target=_do_install, args=(payload_str,), daemon=True).start()


def _do_install(payload_str: str):
    try:
        p = json.loads(payload_str)
    except Exception:
        return

    app_id   = p.get('app_id', 0)
    name     = p.get('name', 'app')
    path     = p.get('path', '')
    args     = p.get('args', '')
    app_type = p.get('type', 'exe')
    task     = f'AP35Install_{app_id}'

    if not path:
        _report(app_id, name, 'error', 'Путь не указан')
        return

    # Для URL — скачать во temp
    local_path = path
    tmp_file = None
    if app_type == 'url' or path.startswith('http://') or path.startswith('https://'):
        ext = os.path.splitext(path.split('?')[0])[1] or '.exe'
        tmp_file = os.path.join(tempfile.gettempdir(), f'ap35_inst_{app_id}{ext}')
        if not _download(path, tmp_file):
            _report(app_id, name, 'error', 'Ошибка скачивания')
            return
        local_path = tmp_file
        app_type = 'exe' if ext.lower() != '.msi' else 'msi'

    # Собрать команду
    if app_type == 'msi':
        cmd = f'msiexec /i "{local_path}" {args} /quiet /norestart'
    elif app_type == 'copy':
        dest = args or 'C:\\Program Files\\'
        cmd = f'cmd /c copy /Y "{local_path}" "{dest}"'
    elif app_type == 'script':
        cmd = f'powershell -ExecutionPolicy Bypass -NonInteractive -File "{local_path}" {args}'
    else:  # exe
        cmd = f'"{local_path}" {args}'

    ok, detail = _run_as_system(cmd, task)

    if tmp_file and os.path.exists(tmp_file):
        try:
            os.remove(tmp_file)
        except Exception:
            pass

    _report(app_id, name, 'ok' if ok else 'error', detail)
