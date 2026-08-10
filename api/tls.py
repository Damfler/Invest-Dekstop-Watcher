"""
tls.py — CA-бандл для запросов к брокерским API.

Зачем: Т-Банк отдаёт TLS-цепочку, выпущенную «Russian Trusted Root CA»
(Минцифры). Этого корня нет ни в бандле certifi (Mozilla CA), который
requests использует по умолчанию, ни в хранилище Windows — поэтому
запросы падают с CERTIFICATE_VERIFY_FAILED: self-signed certificate
in certificate chain.

Решение: склеиваем certifi + корень Минцифры во временный файл и
подсовываем его в session.verify. Доверие ограничено этим приложением —
системное хранилище не трогаем.

Сертификат: assets/certs/russian_trusted_ca.pem, официальная раздача
https://gu-st.ru/content/Other/doc/russiantrustedca.pem
SHA-256 корня: D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31
"""
import os
import sys
import logging
import tempfile
import threading

import certifi

log = logging.getLogger("tbank.tls")

# PyInstaller onefile: ресурсы в sys._MEIPASS, иначе рядом со скриптом
_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_EXTRA_CA = os.path.join(_BASE_DIR, "assets", "certs", "russian_trusted_ca.pem")

_lock = threading.Lock()
_bundle_path: str | None = None


def ca_bundle() -> str:
    """
    Путь к CA-бандлу для verify=. Собирается один раз за процесс.
    При любой ошибке — откат на голый certifi (не хуже прежнего поведения).
    """
    global _bundle_path

    with _lock:
        if _bundle_path and os.path.exists(_bundle_path):
            return _bundle_path

        base = certifi.where()
        if not os.path.exists(_EXTRA_CA):
            log.warning("Доп. CA не найден (%s) — используем только certifi", _EXTRA_CA)
            _bundle_path = base
            return _bundle_path

        try:
            with open(base, "r", encoding="utf-8") as f:
                data = f.read()
            with open(_EXTRA_CA, "r", encoding="utf-8") as f:
                extra = f.read()

            fd, path = tempfile.mkstemp(prefix="stack_ca_", suffix=".pem")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                if not data.endswith("\n"):
                    f.write("\n")
                f.write(extra)

            _bundle_path = path
            log.info("CA-бандл собран: certifi + Russian Trusted Root CA")
        except Exception as e:
            log.warning("Не удалось собрать CA-бандл (%s) — откат на certifi", e)
            _bundle_path = base

        return _bundle_path
