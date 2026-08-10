"""
api.py — T-Bank Invest REST API
- Глобальный throttle между запросами (на экземпляр API)
- Retry: до 8 попыток; 429 — экспоненциальная пауза 5→60 сек + Retry-After
- 401/403 — сразу исключение без retry
- Кэш BondBy в памяти + cooldown после неудачи
"""
import time
import logging
import threading
import requests
from datetime import datetime

from api.endpoints import (
    API_BASE_PROD, API_BASE_SANDBOX,
    GET_ACCOUNTS, GET_PORTFOLIO,
    BOND_BY, SHARE_BY, GET_INSTRUMENT_BY, GET_BOND_COUPONS, GET_DIVIDENDS,
    ID_TYPE_FIGI,
)
from api.tls import ca_bundle
from constants import (
    API_MIN_INTERVAL_SEC, API_MAX_ATTEMPTS,
    API_RATE_LIMIT_BASE, API_RATE_LIMIT_MAX, API_BOND_FAIL_COOLDOWN,
)

log = logging.getLogger("tbank.api")

RETRY_DELAYS = [2, 4, 8]


def _method_name(path: str) -> str:
    """BondBy из полного gRPC-пути."""
    return path.rsplit("/", 1)[-1] if path else path


def _body_hint(body: dict) -> str:
    """Краткий контекст запроса без токена."""
    parts: list[str] = []
    if body.get("accountId"):
        acc = str(body["accountId"])
        parts.append(f"account={acc[:8]}…" if len(acc) > 8 else f"account={acc}")
    if body.get("idType") == ID_TYPE_FIGI and body.get("id"):
        parts.append(f"figi={body['id']}")
    elif body.get("figi"):
        parts.append(f"figi={body['figi']}")
    elif body.get("instrumentId"):
        parts.append(f"figi={body['instrumentId']}")
    return " ".join(parts)


class TBankAPIError(Exception):
    pass


class TBankAPI:
    def __init__(self, token: str, use_sandbox: bool = False, label: str = "Т-Банк"):
        self.base = API_BASE_SANDBOX if use_sandbox else API_BASE_PROD
        self._label = label
        self._env = "sandbox" if use_sandbox else "prod"
        self.session = requests.Session()
        self.session.verify = ca_bundle()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "accept":        "application/json",
        })
        self._throttle_lock = threading.Lock()
        self._last_request_ts = 0.0
        self._bond_cache: dict[str, dict] = {}
        self._bond_fail_until: dict[str, float] = {}
        log.info("API [%s] %s — %s", label, self._env, self.base)

    def _throttle_wait(self):
        with self._throttle_lock:
            now = time.monotonic()
            wait = API_MIN_INTERVAL_SEC - (now - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base}/{path}"
        last_exc: Exception | None = None
        rate_limit_streak = 0
        method = _method_name(path)
        hint = _body_hint(body)

        for attempt in range(API_MAX_ATTEMPTS):
            self._throttle_wait()
            if attempt == 0:
                log.info(
                    "API [%s/%s] → %s%s",
                    self._label, self._env, method,
                    f" ({hint})" if hint else "",
                )
            elif rate_limit_streak == 0:
                log.info(
                    "API [%s/%s] ↻ %s повтор %d/%d%s",
                    self._label, self._env, method,
                    attempt + 1, API_MAX_ATTEMPTS,
                    f" ({hint})" if hint else "",
                )
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
                    rate_limit_streak += 1
                    wait = min(
                        API_RATE_LIMIT_BASE * (2 ** (rate_limit_streak - 1)),
                        API_RATE_LIMIT_MAX,
                    )
                    retry_after = r.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, int(retry_after))
                        except ValueError:
                            pass
                    log.warning(
                        "API [%s/%s] 429 %s, жду %d сек... (попытка %d/%d)%s",
                        self._label, self._env, method, wait,
                        attempt + 1, API_MAX_ATTEMPTS,
                        f" ({hint})" if hint else "",
                    )
                    time.sleep(wait)
                    continue

                rate_limit_streak = 0
                r.raise_for_status()
                return r.json()

            except TBankAPIError:
                raise
            except requests.exceptions.Timeout as e:
                last_exc = e
                log.warning("Таймаут %s (попытка %d/%d)", method, attempt + 1, API_MAX_ATTEMPTS)
            except requests.exceptions.HTTPError as e:
                last_exc = e
                log.warning("HTTP ошибка %s: %s (попытка %d/%d)", method, e, attempt + 1, API_MAX_ATTEMPTS)
            except Exception as e:
                last_exc = e
                log.warning("Ошибка %s: %s (попытка %d/%d)", method, e, attempt + 1, API_MAX_ATTEMPTS)

            if attempt < API_MAX_ATTEMPTS - 1 and rate_limit_streak == 0:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])

        if rate_limit_streak > 0:
            raise TBankAPIError(
                f"Превышен лимит запросов (429) для {method} после {API_MAX_ATTEMPTS} попыток"
            )
        raise TBankAPIError(
            f"Не удалось выполнить запрос после {API_MAX_ATTEMPTS} попыток: {last_exc}"
        )

    # ── Методы API ───────────────────────────────────────────────────────────

    def get_accounts(self) -> list[dict]:
        return self._post(GET_ACCOUNTS, {}).get("accounts", [])

    def get_portfolio(self, account_id: str) -> dict:
        return self._post(GET_PORTFOLIO, {"accountId": account_id, "currency": "RUB"})

    def get_bond_by_figi(self, figi: str) -> dict | None:
        if not figi:
            return None
        if figi in self._bond_cache:
            log.debug("API [%s/%s] BondBy cache hit figi=%s", self._label, self._env, figi)
            return self._bond_cache[figi]
        fail_until = self._bond_fail_until.get(figi, 0)
        if fail_until > time.monotonic():
            log.debug(
                "API [%s/%s] BondBy skip (cooldown) figi=%s", self._label, self._env, figi,
            )
            return None
        try:
            bond = self._post(
                BOND_BY, {"idType": ID_TYPE_FIGI, "id": figi},
            ).get("instrument")
            if bond:
                self._bond_cache[figi] = bond
                self._bond_fail_until.pop(figi, None)
            return bond
        except TBankAPIError as e:
            self._bond_fail_until[figi] = time.monotonic() + API_BOND_FAIL_COOLDOWN
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
            return self._post(
                GET_INSTRUMENT_BY, {"idType": ID_TYPE_FIGI, "id": figi},
            ).get("instrument")
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

    def get_dividends(self, figi: str, from_dt: datetime, to_dt: datetime) -> list[dict]:
        """Получить дивиденды по инструменту (figi) за период."""
        try:
            return self._post(GET_DIVIDENDS, {
                "instrumentId": figi,
                "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to":   to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }).get("dividends", [])
        except Exception as e:
            log.debug("get_dividends(%s): %s", figi, e)
            return []
