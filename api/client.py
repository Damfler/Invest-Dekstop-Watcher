"""
api.py — T-Bank Invest REST API
- Retry: 3 попытки, задержка 2→4→8 сек при 5xx / таймауте
- 429 rate limit: пауза 5→10→15 сек
- 401/403 — сразу исключение без retry
"""
import time
import logging
import requests
from datetime import datetime

from api.endpoints import (
    API_BASE_PROD, API_BASE_SANDBOX,
    GET_ACCOUNTS, GET_PORTFOLIO,
    BOND_BY, SHARE_BY, GET_INSTRUMENT_BY, GET_BOND_COUPONS,
    ID_TYPE_FIGI,
)

log = logging.getLogger("tbank.api")

RETRY_COUNT  = 3
RETRY_DELAYS = [2, 4, 8]


class TBankAPIError(Exception):
    pass


class TBankAPI:
    def __init__(self, token: str, use_sandbox: bool = False):
        self.base = API_BASE_SANDBOX if use_sandbox else API_BASE_PROD
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "accept":        "application/json",
        })
        if use_sandbox:
            log.info("Режим sandbox активен")

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base}/{path}"
        last_exc: Exception | None = None

        for attempt in range(RETRY_COUNT):
            try:
                r = self.session.post(url, json=body, timeout=20)

                if r.status_code == 400:
                    try:
                        detail = r.json().get("message", r.text[:120])
                    except Exception:
                        detail = r.text[:120]
                    raise TBankAPIError(f"HTTP 400 Bad Request: {detail}")

                if r.status_code in (401, 403):
                    raise TBankAPIError(f"HTTP {r.status_code}: проверьте токен")

                if r.status_code == 429:
                    wait = min(5 * (attempt + 1), 15)
                    log.warning("Rate limit 429 %s, жду %d сек...", path.split('/')[-1], wait)
                    time.sleep(wait)
                    continue

                r.raise_for_status()
                return r.json()

            except TBankAPIError:
                raise
            except requests.exceptions.Timeout as e:
                last_exc = e
                log.warning("Таймаут %s (попытка %d/%d)", path, attempt + 1, RETRY_COUNT)
            except requests.exceptions.HTTPError as e:
                last_exc = e
                log.warning("HTTP ошибка %s: %s (попытка %d/%d)", path, e, attempt + 1, RETRY_COUNT)
            except Exception as e:
                last_exc = e
                log.warning("Ошибка %s: %s (попытка %d/%d)", path, e, attempt + 1, RETRY_COUNT)

            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAYS[attempt])

        raise TBankAPIError(f"Не удалось выполнить запрос после {RETRY_COUNT} попыток: {last_exc}")

    # ── Методы API ───────────────────────────────────────────────────────────

    def get_accounts(self) -> list[dict]:
        return self._post(GET_ACCOUNTS, {}).get("accounts", [])

    def get_portfolio(self, account_id: str) -> dict:
        return self._post(GET_PORTFOLIO, {"accountId": account_id, "currency": "RUB"})

    def get_bond_by_figi(self, figi: str) -> dict | None:
        try:
            return self._post(BOND_BY, {"idType": ID_TYPE_FIGI, "id": figi}).get("instrument")
        except TBankAPIError as e:
            log.warning("get_bond_by_figi(%s): %s", figi, e)
            return None
        except Exception as e:
            log.debug("get_bond_by_figi(%s): %s", figi, e)
            return None

    def get_share_by_figi(self, figi: str) -> dict | None:
        try:
            return self._post(SHARE_BY, {"idType": ID_TYPE_FIGI, "id": figi}).get("instrument")
        except Exception as e:
            log.debug("get_share_by_figi(%s): %s", figi, e)
            return None

    def get_instrument_by_figi(self, figi: str) -> dict | None:
        try:
            return self._post(GET_INSTRUMENT_BY, {"idType": ID_TYPE_FIGI, "id": figi}).get("instrument")
        except Exception as e:
            log.debug("get_instrument_by_figi(%s): %s", figi, e)
            return None

    def get_bond_coupons(self, figi: str, from_dt: datetime, to_dt: datetime) -> list[dict]:
        try:
            return self._post(GET_BOND_COUPONS, {
                "figi": figi,
                "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to":   to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }).get("events", [])
        except Exception as e:
            log.debug("get_bond_coupons(%s): %s", figi, e)
            return []
