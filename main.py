"""
main.py — точка входа T-Bank Invest Tray Widget
"""
import logging
import logging.handlers
import os
import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "InvestDesktopWatcher")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
LOG_FILE = os.path.join(BASE_DIR, "tbank_errors.log")


def setup_logging():
    """
    Ротирующий лог: макс 1 МБ, хранится 3 файла.
    INFO+ в файл, WARNING+ в консоль.
    """
    root = logging.getLogger("tbank")
    root.setLevel(logging.DEBUG)

    # Файл — ротирующий
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # Консоль — только WARNING+
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(ch)

    return logging.getLogger("tbank.main")


def reset_config():
    """Сбрасывает конфиг и кэш для повторного прохождения визарда (только dev)."""
    if getattr(sys, 'frozen', False):
        print("--reset недоступен в .exe режиме")
        sys.exit(1)

    import json
    from constants import TOKEN_STUB

    base = os.path.dirname(os.path.abspath(__file__))
    config_file    = os.path.join(base, "config.json")
    dismissed_file = os.path.join(base, "dismissed.json")
    cache_file     = os.path.join(base, "cache.json")

    removed = []

    # Сбрасываем connections в конфиге (остальные настройки сохраняем)
    if os.path.exists(config_file):
        try:
            with open(config_file, encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["connections"] = [
                {"name": "Т-Банк", "broker": "tbank",
                 "token": TOKEN_STUB, "enabled": True, "use_sandbox": False}
            ]
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            removed.append("config.json (connections сброшены)")
        except Exception as e:
            print(f"Не удалось сбросить config.json: {e}")
    else:
        removed.append("config.json отсутствовал")

    for fpath, label in [(dismissed_file, "dismissed.json"), (cache_file, "cache.json")]:
        if os.path.exists(fpath):
            os.remove(fpath)
            removed.append(label)

    print("Сброс выполнен:")
    for item in removed:
        print(f"  • {item}")
    print("\nПерезапустите: python main.py")


def main():
    if "--reset" in sys.argv:
        reset_config()
        sys.exit(0)

    log = setup_logging()

    try:
        from PIL import Image
        import pystray
    except ImportError:
        print("Установите зависимости: pip install -r requirements.txt")
        sys.exit(1)

    from core.config import load_config
    from core.data_store import DataStore
    from core.app import TBankTrayApp
    from ui.wizard import needs_wizard, run_wizard

    cfg = load_config()

    # Мастер первого запуска — если токен не введён
    if needs_wizard(cfg):
        log.info("Запуск мастера первого запуска")
        token = run_wizard()
        if not token:
            log.info("Мастер отменён пользователем")
            sys.exit(0)
        cfg = load_config()   # перечитываем — wizard сохранил токен

    # Создаём API для каждого активного подключения
    from constants import TOKEN_STUB
    connections = cfg.get("connections", [])
    apis = []
    for conn in connections:
        if not conn.get("enabled", True):
            continue
        broker = conn.get("broker", "tbank")
        token  = conn.get("token", "")
        if not token or token == TOKEN_STUB:
            continue
        if broker == "tbank":
            from api.client import TBankAPI
            apis.append((
                conn.get("name", "Т-Банк"),
                TBankAPI(token, use_sandbox=conn.get("use_sandbox", False)),
            ))
        else:
            log.warning("Неизвестный брокер '%s' в подключении '%s' — пропускаем",
                        broker, conn.get("name", "?"))

    if not apis:
        log.error("Нет активных подключений с токеном. Проверьте config.json.")
        sys.exit(1)

    store = DataStore(apis, cfg)
    app   = TBankTrayApp(cfg, store)

    try:
        app.run()
    except KeyboardInterrupt:
        log.info("Прерывание пользователем")
    except Exception:
        log.exception("Неожиданная ошибка:")
        raise


if __name__ == "__main__":
    main()
