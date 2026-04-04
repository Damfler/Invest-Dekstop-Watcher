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


def main():
    log = setup_logging()

    try:
        from PIL import Image
        import pystray
    except ImportError:
        print("Установите зависимости: pip install -r requirements.txt")
        sys.exit(1)

    from config import load_config
    from data_store import DataStore
    from app import TBankTrayApp
    from wizard import needs_wizard, run_wizard

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
            from api import TBankAPI
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
