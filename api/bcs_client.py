"""
bcs_client.py — клиент BCS Trade API (read-only).

Refresh-токен из ЛК БКС → access-токен (OAuth2, 24 ч).
Интерфейс совместим с TBankAPI для DataStore.
"""
import logging
import threading
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from api.bcs_endpoints import (
    AUTH_URL, PORTFOLIO_BASE, LIMITS_BASE, INFO_BASE,
    CLIENT_ID_READ, CLIENT_ID_WRITE,
    BOND_CLASS_CODES, ETF_CLASS_CODES, CURRENCY_CLASS,
)
from constants import (
    API_MIN_INTERVAL_SEC, API_MAX_ATTEMPTS,
    API_RATE_LIMIT_BASE, API_RATE_LIMIT_MAX,
)
from api.bcs_api_dump import dump_api_response, dump_dir
from utils.moex_iss import (
    bond_coupons as _moex_bond_coupons,
    dividends as _moex_dividends,
    bond_static as _moex_bond_static,
)
from version import APP_VERSION

log = logging.getLogger("stack.bcs")

RETRY_DELAYS = [2, 4, 8]
_ACCOUNT_ID  = "bcs-main"
_USER_AGENT  = f"Stack/{APP_VERSION}"


def _is_position_dict(obj: dict) -> bool:
    return any(k in obj for k in ("ticker", "secCode", "classCode", "board", "marketValue", "currentValue", "quantity"))


def _is_currency_ticker(ticker: str) -> bool:
    t = (ticker or "").upper()
    if not t:
        return False
    if t in {"USD", "EUR", "CNY", "GBP", "CHF", "HKD", "TRY", "RUB", "SUR"}:
        return True
    if "UTSTOM" in t or "_TOM" in t or t.endswith("TOM"):
        return True
    for cur in ("USD", "EUR", "CNY", "GBP"):
        if cur in t and ("RUB" in t or "TOM" in t):
            return True
    return False


def _class_codes_to_try(class_code: str, ticker: str) -> list[str]:
    cc = (class_code or "").upper()
    if cc:
        return [cc]
    if _is_currency_ticker(ticker):
        return ["CETS", "CNGD"]
    return ["TQBR", "SPBXM", "TQTF", "TQOB", "TQCB", "CETS"]


def _merge_bcs_positions(rows: list) -> list[dict]:
    """Схлопывает дубли (массив-снимков портфеля) и агрегирует раздельные лоты."""
    by_key: dict[tuple[str, str], dict] = {}
    for p in rows:
        if not isinstance(p, dict):
            continue
        cc = (p.get("classCode") or p.get("board") or "").upper()
        ticker = (p.get("ticker") or p.get("secCode") or "").upper()
        if not ticker:
            continue
        key = (cc, ticker)
        mv = float(
            p.get("marketValue")
            or p.get("currentValueRub")
            or p.get("currentValue")
            or p.get("balanceValueRub")
            or p.get("balanceValue")
            or 0
        )
        if key not in by_key:
            by_key[key] = dict(p)
            continue
        prev = by_key[key]
        prev_mv = float(
            prev.get("marketValue")
            or prev.get("currentValueRub")
            or prev.get("currentValue")
            or prev.get("balanceValueRub")
            or prev.get("balanceValue")
            or 0
        )
        if abs(mv - prev_mv) < 0.01 and mv > 0:
            continue
        # Складываем в marketValue, чтобы остальная логика (summary и т.п.) не ломалась.
        prev["marketValue"] = prev_mv + mv
        prev_pl = float(prev.get("profitLoss") or prev.get("unrealizedPL") or 0)
        cur_pl = float(p.get("profitLoss") or p.get("unrealizedPL") or 0)
        prev["profitLoss"] = prev_pl + cur_pl
        # quantity может быть float или {"value": ...}
        q_prev = prev.get("quantity")
        q_cur = p.get("quantity")
        try:
            q_prev_v = float(q_prev.get("value") if isinstance(q_prev, dict) else (q_prev or 0))
        except (TypeError, ValueError):
            q_prev_v = 0.0
        try:
            q_cur_v = float(q_cur.get("value") if isinstance(q_cur, dict) else (q_cur or 0))
        except (TypeError, ValueError):
            q_cur_v = 0.0
        prev["quantity"] = q_prev_v + q_cur_v
    return list(by_key.values())


def _flatten_portfolio_list(raw: list) -> list[dict]:
    """Разворачивает list-ответ BCS: снимки {positions,summary} или плоские позиции."""
    if not raw:
        return []
    first = raw[0]
    if isinstance(first, dict) and ("positions" in first or "summary" in first):
        out: list[dict] = []
        summary: dict = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            if item.get("positions"):
                out.extend(item["positions"])
            if item.get("summary") and not summary:
                summary = item["summary"]
        if out:
            return _merge_bcs_positions(out)
        if isinstance(first.get("positions"), list):
            return _merge_bcs_positions(first["positions"])
    if isinstance(first, dict) and _is_position_dict(first):
        rows = [p for p in raw if isinstance(p, dict)]
        # Новый bff-portfolio отдаёт одинаковые позиции по term (T0/T1/T2/T365).
        # Для отображения портфеля берём один "срез": предпочтительно T0, иначе T365.
        terms = {str(p.get("term") or "") for p in rows}
        if "T0" in terms:
            rows = [p for p in rows if str(p.get("term") or "") == "T0"]
        elif "T365" in terms:
            rows = [p for p in rows if str(p.get("term") or "") == "T365"]
        return _merge_bcs_positions(rows)
    return []


def _normalize_portfolio_raw(raw) -> tuple[list, dict]:
    """
    BCS /portfolio может вернуть:
    - {"positions": [...], "summary": {...}}
    - [] или [{positions, summary}] — пустой/обёрнутый ответ
    - [...] — массив позиций без summary
    """
    if isinstance(raw, list):
        if not raw:
            return [], {}
        first = raw[0]
        flat = _flatten_portfolio_list(raw)
        if flat:
            total = sum(
                float(
                    p.get("marketValue")
                    or p.get("currentValueRub")
                    or p.get("currentValue")
                    or p.get("balanceValueRub")
                    or p.get("balanceValue")
                    or 0
                )
                for p in flat
            )
            pl = sum(float(p.get("profitLoss") or p.get("unrealizedPL") or 0) for p in flat)
            summary: dict = {"totalValue": total, "profitLoss": pl}
            if isinstance(first, dict) and isinstance(first.get("summary"), dict):
                summary = {**summary, **first["summary"]}
            return flat, summary
        if isinstance(first, dict) and ("positions" in first or "summary" in first):
            return first.get("positions") or [], first.get("summary") or {}
        raise BCSAPIError(f"Неожиданный формат портфеля (list[{type(first).__name__}])")

    if isinstance(raw, dict):
        if "positions" not in raw and isinstance(raw.get("data"), dict):
            raw = raw["data"]
        if "positions" not in raw and "summary" not in raw and _is_position_dict(raw):
            positions = [raw]
            total = float(raw.get("marketValue") or 0)
            pl = float(raw.get("profitLoss") or raw.get("unrealizedPL") or 0)
            return positions, {"totalValue": total, "profitLoss": pl}
        return raw.get("positions") or [], raw.get("summary") or {}

    raise BCSAPIError(f"Неожиданный ответ портфеля ({type(raw).__name__})")


def _build_http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/json"})
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class BCSAPIError(Exception):
    pass


def bcs_figi(class_code: str, ticker: str) -> str:
    return f"bcs:{class_code}:{ticker}"


def parse_bcs_figi(figi: str) -> tuple[str, str] | None:
    if not figi or not figi.startswith("bcs:"):
        return None
    parts = figi.split(":", 2)
    if len(parts) != 3:
        return None
    return parts[1], parts[2]


def _float_to_money(v: float | None) -> dict:
    v = float(v or 0)
    sign = -1 if v < 0 else 1
    v = abs(v)
    units = int(v)
    nano = int(round((v - units) * 1_000_000_000))
    if sign < 0:
        units = -units
        nano = -nano
    return {"units": units, "nano": nano}


def _class_to_itype(class_code: str, inst_type: str = "") -> str:
    if inst_type:
        t = str(inst_type).upper()
        _map = {
            "STOCK": "share", "SHARE": "share", "BOND": "bond", "ETF": "etf",
            "FUND": "etf", "CURRENCY": "currency", "FUTURE": "futures",
            "FUTURES": "futures", "OPTION": "option",
        }
        if t in _map:
            return _map[t]
        t_lower = inst_type.lower()
        if t_lower in ("bond", "share", "etf", "currency", "futures"):
            return "share" if t_lower == "stock" else t_lower
    cc = (class_code or "").upper()
    if cc in BOND_CLASS_CODES:
        return "bond"
    if cc in ETF_CLASS_CODES:
        return "etf"
    if cc in CURRENCY_CLASS:
        return "currency"
    if cc.startswith("SPBFUT") or cc.startswith("FUT") or cc == "OPTEXP":
        return "futures"
    return "share"


def _bcs_position_value(p: dict, itype: str, qty) -> tuple[float, float]:
    """
    Возвращает (цена_за_единицу_в_руб, стоимость_в_руб).
    У облигаций marketPrice — % от номинала, поэтому опираемся на marketValue.
    """
    # Старый формат: marketValue/marketPrice
    market_value = float(p.get("marketValue") or 0)
    market_price = float(p.get("marketPrice") or 0)

    # Новый формат bff-portfolio: currentValue/currentPrice (+ Rub/Usd/Eur variants)
    if not market_value:
        market_value = float(
            p.get("currentValueRub")
            or p.get("currentValue")
            or p.get("balanceValueRub")
            or p.get("balanceValue")
            or 0
        )
    if not market_price:
        market_price = float(p.get("currentPrice") or p.get("balancePrice") or 0)
    try:
        q = float(qty)
    except (TypeError, ValueError):
        q = 0.0

    if market_value and q:
        return market_value / q, market_value
    if market_value:
        return market_price, market_value
    if market_price and q and itype != "bond":
        return market_price, market_price * q
    return market_price, 0.0


class BCSAPI:
    """BCS Trade API — refresh-токен, read-only scope."""

    broker = "bcs"

    def __init__(self, refresh_token: str, label: str = "БКС",
                 client_id: str = CLIENT_ID_READ):
        self._refresh_token = (refresh_token or "").strip().strip('"').strip("'")
        self._client_id = client_id
        self._label = label
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()
        self._throttle_lock = threading.Lock()
        self._last_request_ts = 0.0
        self._instrument_cache: dict[str, dict] = {}
        self._info_service_disabled = False
        self._account_name = label
        self._session = _build_http_session()
        log.info("API [%s] prod — BCS Trade API", label)
        # Дампы BCS выключены по умолчанию (включаются env BCS_API_DUMP=1)

    # ── OAuth2 ────────────────────────────────────────────────────────────────

    def _oauth_with_client(self, client_id: str) -> None:
        data = {
            "client_id":     client_id,
            "grant_type":    "refresh_token",
            "refresh_token": self._refresh_token,
        }
        try:
            r = self._session.post(
                AUTH_URL, data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except requests.RequestException as e:
            raise BCSAPIError(f"Ошибка авторизации БКС: {e}") from e

        if r.status_code == 401:
            raise BCSAPIError(
                "Refresh-токен БКС недействителен или истёк (90 дней). "
                "Выпустите новый в ЛК: Профиль → Токены API"
            )
        if r.status_code != 200:
            dump_api_response(
                label="OAuth token",
                method="POST",
                url=AUTH_URL,
                status_code=r.status_code,
                body_text=r.text,
                error=f"HTTP {r.status_code}",
                redact_tokens=True,
            )
            detail = r.text[:200]
            raise BCSAPIError(f"OAuth HTTP {r.status_code}: {detail}")

        dump_api_response(
            label="OAuth token",
            method="POST",
            url=AUTH_URL,
            status_code=r.status_code,
            body_text=r.text,
            redact_tokens=True,
        )
        body = r.json()
        token = body.get("access_token")
        if not token:
            raise BCSAPIError("OAuth: access_token отсутствует в ответе")

        expires_in = int(body.get("expires_in", 86400))
        self._client_id = client_id
        self._access_token = token
        self._token_expires_at = time.monotonic() + max(expires_in - 120, 60)
        if body.get("refresh_token"):
            self._refresh_token = body["refresh_token"]

    def _refresh_access_token(self):
        log.info("API [%s/prod] → OAuth token refresh", self._label)
        order = [self._client_id, CLIENT_ID_READ, CLIENT_ID_WRITE]
        seen: set[str] = set()
        client_ids = [c for c in order if c and not (c in seen or seen.add(c))]

        last_err: BCSAPIError | None = None
        for client_id in client_ids:
            try:
                self._oauth_with_client(client_id)
                if client_id != order[0]:
                    log.info("API [%s] OAuth: client_id=%s", self._label, client_id)
                return
            except BCSAPIError as e:
                last_err = e
                if "401" in str(e):
                    raise
                log.debug("OAuth client_id=%s: %s", client_id, e)
        if last_err:
            raise last_err
        raise BCSAPIError("Не удалось авторизоваться в BCS Trade API")

    def _ensure_token(self):
        with self._token_lock:
            if self._access_token and time.monotonic() < self._token_expires_at:
                return
            self._refresh_access_token()

    def _throttle_wait(self):
        with self._throttle_lock:
            now = time.monotonic()
            wait = API_MIN_INTERVAL_SEC - (now - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    def _request(self, method: str, url: str, *,
                 params: dict | None = None, json_body: dict | None = None,
                 label: str = "") -> dict | list:
        last_exc: Exception | None = None
        rate_streak = 0
        tag = label or url.rsplit("/", 1)[-1]

        for attempt in range(API_MAX_ATTEMPTS):
            self._ensure_token()
            self._throttle_wait()
            if attempt == 0:
                log.info("API [%s/prod] → %s", self._label, tag)
            try:
                r = self._session.request(
                    method, url,
                    params=params, json=json_body,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept":        "application/json",
                    },
                    timeout=(10, 45),
                )

                if r.status_code == 401 and attempt == 0:
                    self._access_token = None
                    self._ensure_token()
                    continue

                if r.status_code == 429:
                    rate_streak += 1
                    wait = min(
                        API_RATE_LIMIT_BASE * (2 ** (rate_streak - 1)),
                        API_RATE_LIMIT_MAX,
                    )
                    ra = r.headers.get("Retry-After")
                    if ra:
                        try:
                            wait = max(wait, int(ra))
                        except ValueError:
                            pass
                    log.warning(
                        "API [%s/prod] 429 %s, жду %d сек...", self._label, tag, wait,
                    )
                    time.sleep(wait)
                    continue

                if r.status_code in (401, 403):
                    dump_api_response(
                        label=tag, method=method, url=url, params=params,
                        status_code=r.status_code, body_text=r.text,
                        error=str(r.status_code),
                    )
                    raise BCSAPIError(f"HTTP {r.status_code}: проверьте refresh-токен БКС")

                if r.status_code >= 400:
                    dump_api_response(
                        label=tag, method=method, url=url, params=params,
                        status_code=r.status_code, body_text=r.text,
                        error=str(r.status_code),
                    )
                    raise BCSAPIError(f"HTTP {r.status_code}: {r.text[:160]}")

                rate_streak = 0
                dump_api_response(
                    label=tag, method=method, url=url, params=params,
                    status_code=r.status_code, body_text=r.text or "{}",
                )
                if not r.text:
                    return {}
                return r.json()

            except BCSAPIError:
                raise
            except requests.exceptions.SSLError as e:
                last_exc = e
                wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)] + 1
                log.warning(
                    "API [%s/prod] SSL %s (попытка %d/%d), жду %d сек...",
                    self._label, tag, attempt + 1, API_MAX_ATTEMPTS, wait,
                )
                if attempt < API_MAX_ATTEMPTS - 1:
                    time.sleep(wait)
            except requests.RequestException as e:
                last_exc = e
                log.warning(
                    "API [%s/prod] ошибка %s (попытка %d/%d): %s",
                    self._label, tag, attempt + 1, API_MAX_ATTEMPTS, e,
                )
                if attempt < API_MAX_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])

        raise BCSAPIError(
            f"Не удалось выполнить запрос {tag} после {API_MAX_ATTEMPTS} попыток: {last_exc}"
        )

    def _get(self, url: str, params: dict | None = None, label: str = "") -> dict | list:
        return self._request("GET", url, params=params, label=label)

    # ── Интерфейс DataStore (как TBankAPI) ───────────────────────────────────

    def get_accounts(self) -> list[dict]:
        """Один refresh-токен = один счёт."""
        self._ensure_token()
        return [{
            "id":   _ACCOUNT_ID,
            "name": self._account_name,
            "type": "БКС",
        }]

    def _limits_qty_maps(self, limits: dict) -> tuple[dict[tuple[str, str], float], dict[str, float]]:
        """depo (classCode, secCode) → qty; money currency → qty."""
        depo: dict[tuple[str, str], float] = {}
        money: dict[str, float] = {}
        for row in limits.get("depoLimit") or []:
            if not isinstance(row, dict):
                continue
            cc = (row.get("classCode") or "").upper()
            sec = (row.get("secCode") or row.get("ticker") or "").upper()
            if not sec:
                continue
            # Старый формат: currentBalance/free
            # Новый формат: quantity={type,value}
            q_obj = row.get("quantity")
            bal = row.get("currentBalance")
            if bal is None:
                bal = row.get("free")
            try:
                if isinstance(q_obj, dict):
                    qty = float(q_obj.get("value") or 0)
                else:
                    qty = float(bal or 0)
            except (TypeError, ValueError):
                qty = 0.0
            if qty:
                depo[(cc, sec)] = qty
        for row in limits.get("moneyLimits") or []:
            if not isinstance(row, dict):
                continue
            cur = (row.get("currency") or row.get("currencyCode") or "").upper()
            if not cur:
                continue
            try:
                q_obj = row.get("quantity")
                if isinstance(q_obj, dict):
                    bal = float(q_obj.get("value") or 0)
                else:
                    bal = float(row.get("currentBalance") or row.get("balance") or row.get("quantity") or 0)
            except (TypeError, ValueError):
                bal = 0.0
            if bal:
                money[cur] = bal
        return depo, money

    def _qty_from_limits(
        self,
        depo_map: dict[tuple[str, str], float],
        class_code: str,
        ticker: str,
        portfolio_qty: float,
    ) -> float:
        cc = (class_code or "").upper()
        t = ticker.upper()
        candidates = [(k, v) for k, v in depo_map.items() if k[1] == t]
        if not candidates:
            return portfolio_qty
        if cc:
            for k, v in candidates:
                if k[0] == cc:
                    return v
        if len(candidates) == 1:
            return candidates[0][1]
        return portfolio_qty

    def get_portfolio(self, account_id: str) -> dict:
        raw = self._get(f"{PORTFOLIO_BASE}/portfolio", label="Portfolio")
        positions_raw, summary = _normalize_portfolio_raw(raw)
        positions_raw = _merge_bcs_positions(positions_raw)

        limits_raw: dict = {}
        depo_map: dict[tuple[str, str], float] = {}
        money_map: dict[str, float] = {}
        try:
            limits_raw = self._get(f"{LIMITS_BASE}/limits", label="Limits")
            if isinstance(limits_raw, dict) and isinstance(limits_raw.get("data"), dict):
                limits_raw = limits_raw["data"]
            if isinstance(limits_raw, dict):
                depo_map, money_map = self._limits_qty_maps(limits_raw)
        except BCSAPIError as e:
            log.warning("API [%s] limits недоступны, qty из portfolio: %s", self._label, e)

        total = float(summary.get("totalValue") or 0)
        alltime = float(summary.get("profitLoss") or 0)
        day = float(
            summary.get("dailyProfitLoss")
            or summary.get("profitLossDaily")
            or summary.get("dayProfitLoss")
            or 0
        )

        positions = []
        pos_total = 0.0
        seen_money: set[str] = set()

        for p in positions_raw:
            # BCS может отдавать classCode (старый формат) или board (новый bff-portfolio)
            class_code = p.get("classCode") or p.get("board") or ""
            ticker = p.get("ticker") or p.get("secCode") or ""
            market_value = float(
                p.get("marketValue")
                or p.get("currentValueRub")
                or p.get("currentValue")
                or p.get("balanceValueRub")
                or p.get("balanceValue")
                or 0
            )
            if not ticker:
                if market_value > 0:
                    ticker = (p.get("currency") or "CASH").upper()
                else:
                    continue

            try:
                q_obj = p.get("quantity", 0)
                if isinstance(q_obj, dict):
                    portfolio_qty = float(q_obj.get("value") or 0)
                else:
                    portfolio_qty = float(q_obj or 0)
            except (TypeError, ValueError):
                portfolio_qty = 0.0

            inst = self._resolve_instrument(class_code, ticker)
            if inst:
                class_code = inst.get("classCode") or class_code
                isin = p.get("isin") or inst.get("isin", "")
                name = inst.get("shortName") or inst.get("name") or p.get("displayName") or p.get("name") or ticker
                itype = _class_to_itype(class_code, inst.get("type", ""))
            else:
                isin = p.get("isin") or ""
                name = p.get("displayName") or p.get("name") or p.get("shortName") or ticker
                itype = _class_to_itype(class_code, p.get("type", ""))
                if _is_currency_ticker(ticker):
                    itype = "currency"
                # Новый bff-portfolio отдаёт instrumentType=STOCK/BOND/CURRENCY
                it_raw = (p.get("instrumentType") or "").upper()
                if it_raw in ("STOCK", "SHARE"):
                    itype = "share"
                elif it_raw == "BOND":
                    itype = "bond"
                elif it_raw in ("ETF", "FUND"):
                    itype = "etf"
                elif it_raw in ("CURRENCY", "MONEY"):
                    itype = "currency"

            # Для валюты, когда class_code пустой — даём дефолт (нужно для figi)
            if not class_code and itype == "currency":
                class_code = "CETS"

            qty_units = self._qty_from_limits(depo_map, class_code, ticker, portfolio_qty)
            if qty_units != portfolio_qty:
                log.debug(
                    "API [%s] %s/%s qty: portfolio=%s limits=%s",
                    self._label, class_code, ticker, portfolio_qty, qty_units,
                )

            unit_price, pos_value = _bcs_position_value(p, itype, qty_units)
            if itype == "currency" and qty_units > 0 and market_value > 0:
                unit_price = market_value / qty_units
                cur_code = (inst or {}).get("currency", "").upper()
                if cur_code:
                    seen_money.add(cur_code)

            pos_pl = float(p.get("profitLoss") or p.get("unrealizedPL") or 0)
            pos_day = float(
                p.get("dailyProfitLoss") or p.get("profitLossDaily") or p.get("dailyPL") or 0
            )
            figi = bcs_figi(class_code, ticker)

            pos_total += pos_value
            positions.append({
                "instrumentType": itype,
                "figi":           figi,
                "isin":           isin,
                "name":           name,
                "ticker":         ticker,
                # BCS bff-portfolio отдаёт прямую ссылку на лого
                "logo_url":       p.get("logoLink") or "",
                "quantity":       _float_to_money(qty_units),
                "currentPrice":   _float_to_money(unit_price),
                "currentValue":   _float_to_money(pos_value),
                "currentNkd":     _float_to_money(0),
                "expectedYield":  _float_to_money(pos_pl),
                "dailyYield":     _float_to_money(pos_day),
            })

        cash = float(summary.get("cash") or 0)
        if cash > 0 and (not total or total > pos_total + 0.01):
            pos_total += cash
            positions.append({
                "instrumentType": "currency",
                "figi":           "bcs:CETS:RUB",
                "isin":           "",
                "name":           "Денежные средства",
                "ticker":         "RUB",
                "quantity":       _float_to_money(cash),
                "currentPrice":   _float_to_money(1),
                "currentValue":   _float_to_money(cash),
                "currentNkd":     _float_to_money(0),
                "expectedYield":  _float_to_money(0),
                "dailyYield":     _float_to_money(0),
            })

        if not total and positions:
            total = pos_total
        if not alltime and positions:
            alltime = sum(
                float(p.get("profitLoss") or 0)
                for p in positions_raw
                if isinstance(p, dict)
            )

        return {
            "totalAmountPortfolio": _float_to_money(total),
            "dailyYield":           _float_to_money(day),
            "expectedYield":      _float_to_money(alltime),
            "positions":            positions,
        }

    def _fetch_instrument(self, class_code: str, ticker: str) -> dict | None:
        if self._info_service_disabled:
            return None
        for cc in _class_codes_to_try(class_code, ticker):
            key = f"{cc}:{ticker}"
            if key in self._instrument_cache:
                return self._instrument_cache[key]
            try:
                data = self._get(
                    f"{INFO_BASE}/instruments/by-ticker",
                    params={"classCode": cc, "ticker": ticker},
                    label=f"Instrument {ticker}",
                )
                inst = data.get("instrument") if isinstance(data, dict) else None
                if inst:
                    self._instrument_cache[key] = inst
                    return inst
            except BCSAPIError as e:
                # Информационный сервис может быть недоступен/не включен.
                # Чтобы не спамить 404-дампами на каждый тикер — отключаем после первого 404.
                if "HTTP 404" in str(e):
                    self._info_service_disabled = True
                log.debug("instrument(%s/%s): %s", cc, ticker, e)
        return None

    def _resolve_instrument(self, class_code: str, ticker: str) -> dict | None:
        return self._fetch_instrument(class_code, ticker)

    def _resolve_figi(self, figi: str) -> dict | None:
        parsed = parse_bcs_figi(figi)
        if not parsed:
            return None
        class_code, ticker = parsed
        inst = self._fetch_instrument(class_code, ticker)
        if not inst:
            return {"ticker": ticker, "classCode": class_code, "figi": figi}
        itype = _class_to_itype(class_code, inst.get("type", ""))
        return {
            "name":       inst.get("name") or inst.get("shortName") or ticker,
            "ticker":     inst.get("ticker") or ticker,
            "isin":       inst.get("isin", ""),
            "figi":       figi,
            "classCode":  class_code,
            "instrumentType": itype,
            "type":       itype,
        }

    def get_bond_by_figi(self, figi: str) -> dict | None:
        info = self._resolve_figi(figi)
        if not info:
            return None
        if info.get("instrumentType") != "bond" and info.get("type") != "bond":
            cc = info.get("classCode", "")
            if cc not in BOND_CLASS_CODES:
                return None
        # Догружаем статические поля облигации из MOEX ISS, чтобы работали события/аналитика.
        secid = (info.get("ticker") or "").upper()
        if secid:
            moex = _moex_bond_static(secid)
            if moex:
                merged = dict(info)
                merged.update({k: v for k, v in moex.items() if v is not None})
                merged["instrumentType"] = "bond"
                merged["type"] = "bond"
                return merged
        return info

    def get_instrument_by_figi(self, figi: str) -> dict | None:
        return self._resolve_figi(figi)

    def get_share_by_figi(self, figi: str) -> dict | None:
        info = self._resolve_figi(figi)
        if info and info.get("instrumentType") == "share":
            return info
        return None

    def get_bond_coupons(self, figi: str, from_dt: datetime, to_dt: datetime) -> list[dict]:
        """
        BCS Trade API не предоставляет график купонов.
        Догружаем из MOEX ISS (для MOEX-бумаг).
        """
        parsed = parse_bcs_figi(figi)
        if not parsed:
            return []
        _class_code, ticker = parsed
        return _moex_bond_coupons(ticker, from_dt=from_dt, to_dt=to_dt)

    def get_dividends(self, figi: str, from_dt: datetime, to_dt: datetime) -> list[dict]:
        """
        BCS Trade API не предоставляет календарь дивидендов.
        Догружаем из MOEX ISS (для MOEX-бумаг).
        """
        parsed = parse_bcs_figi(figi)
        if not parsed:
            return []
        _class_code, ticker = parsed
        return _moex_dividends(ticker, from_dt=from_dt, to_dt=to_dt)

    def ping(self) -> bool:
        """Проверка подключения (для визарда)."""
        self.get_portfolio(_ACCOUNT_ID)
        return True
