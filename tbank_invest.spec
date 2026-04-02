# tbank_invest.spec
# PyInstaller spec-файл для сборки T-Bank Invest Tray в один .exe
#
# Использование:
#   pyinstaller tbank_invest.spec
#
# Или через build.bat (рекомендуется)

import os, sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
BASE = os.path.abspath('.')

# ── Дополнительные данные ────────────────────────────────────────────────────
datas = [
    # Папка с иконками
    (os.path.join(BASE, 'icons', 'positive.png'), 'icons'),
    (os.path.join(BASE, 'icons', 'negative.png'), 'icons'),
]

# Опциональные иконки (warn / crit) — добавляем если есть
for name in ('warn.png', 'crit.png'):
    p = os.path.join(BASE, 'icons', name)
    if os.path.exists(p):
        datas.append((p, 'icons'))

# HTML-дашборд
datas.append((os.path.join(BASE, 'dashboard.html'), '.'))

# plyer — нужен для toast-уведомлений
datas += collect_data_files('plyer', include_py_files=True)

# pywebview — нужен для HTML-окна (если установлен)
try:
    import webview
    datas += collect_data_files('webview')
except ImportError:
    pass

# ── Hidden imports ───────────────────────────────────────────────────────────
hidden_imports = [
    'pystray._win32',
    'PIL._imaging',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'plyer.platforms.win.notification',
    'win32api', 'win32con', 'win32gui',
    'pkg_resources.py2_compat',
    'requests',
    'requests.packages.urllib3',
    'certifi',
]

try:
    import webview
    hidden_imports += collect_submodules('webview')
    hidden_imports += ['webview.platforms.winforms']
except ImportError:
    pass

# ── Анализ ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[BASE],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'IPython', 'jupyter', 'notebook',
        'tkinter.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tbank_invest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,             # сжатие UPX если установлен
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # без окна консоли
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Иконка .ico (если есть рядом со spec-файлом)
    icon='icons\\positive.ico' if os.path.exists('icons\\positive.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
