# stack.spec
# PyInstaller spec — сборка Stack в один .exe
#
# Использование:
#   pyinstaller stack.spec
# Или через build.bat (рекомендуется)

import os, sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
BASE = os.path.abspath('.')

# ── version_info.txt из version.py ──────────────────────────────────────────
_gen = os.path.join(BASE, 'tools', 'gen_version_info.py')
if os.path.exists(_gen):
    import subprocess
    subprocess.run([sys.executable, _gen], check=True, cwd=BASE)

# ── Конвертация icon.png → icon.ico ─────────────────────────────────────────
_icon_png = os.path.join(BASE, 'assets', 'icons', 'icon.png')
_icon_ico = os.path.join(BASE, 'assets', 'icons', 'icon.ico')
if os.path.exists(_icon_png) and not os.path.exists(_icon_ico):
    try:
        from PIL import Image
        img = Image.open(_icon_png).convert("RGBA")
        img.save(_icon_ico, format="ICO",
                 sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        print(f"[spec] icon.png -> icon.ico")
    except Exception as e:
        print(f"[spec] Cannot convert icon: {e}")

# ── Дополнительные данные ────────────────────────────────────────────────────
datas = []

# Иконки из assets/icons/ (PNG для трея + SVG-источник логотипа)
# Каждая state-иконка имеет 2 варианта: <name>.png (для тёмного taskbar)
# и <name>-light.png (для светлого taskbar Windows). Code выбирает
# нужный автоматически по `SystemUsesLightTheme` в реестре.
_icon_names = []
for base in ('positive', 'negative', 'neutral', 'warn', 'crit', 'icon'):
    _icon_names += [f'{base}.png', f'{base}-light.png']
_icon_names.append('logo.svg')
for name in _icon_names:
    p = os.path.join(BASE, 'assets', 'icons', name)
    if os.path.exists(p):
        datas.append((p, os.path.join('assets', 'icons')))

# SVG-иконки брокеров (показываются в выпадашке "Все счета" в дашборде)
_banks_dir = os.path.join(BASE, 'assets', 'icons', 'banks')
if os.path.isdir(_banks_dir):
    for fname in os.listdir(_banks_dir):
        if fname.lower().endswith('.svg'):
            datas.append((os.path.join(_banks_dir, fname),
                          os.path.join('assets', 'icons', 'banks')))

# HTML-дашборд
datas.append((os.path.join(BASE, 'assets', 'dashboard.html'), 'assets'))

# Корневой CA Минцифры — Т-Банк отдаёт цепочку, которой нет в certifi
_ca_pem = os.path.join(BASE, 'assets', 'certs', 'russian_trusted_ca.pem')
if os.path.exists(_ca_pem):
    datas.append((_ca_pem, os.path.join('assets', 'certs')))

# plyer — toast-уведомления
datas += collect_data_files('plyer', include_py_files=True)

# pywebview — HTML-окно
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
    # Наши пакеты
    'core', 'core.app', 'core.data_store', 'core.config', 'core.cache',
    'api', 'api.client', 'api.endpoints',
    'ui', 'ui.window', 'ui.menu', 'ui.wizard', 'ui.icons',
    'utils', 'utils.formatting', 'utils.analytics', 'utils.notifications',
    'utils.autostart', 'utils.updater',
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
    name='Stack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(_icon_ico if os.path.exists(_icon_ico)
          else os.path.join('assets', 'icons', 'positive.ico')
          if os.path.exists(os.path.join('assets', 'icons', 'positive.ico'))
          else None),
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
