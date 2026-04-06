"""
data_store.py — загрузка данных из API и хранение в памяти.
Вся работа с API происходит здесь; menu.py только читает.
"""
import logging
import threading
from datetime import datetime, timezone, timedelta

from api.client import TBankAPIError
from api.endpoints import LOGO_CDN
from utils.formatting import money_value, parse_ts, days_until, alert_key
import time as _time
from core.cache import save_cache, load_cache, save_history, load_history
from core.config import load_dismissed, save_dismissed
from constants import ALERT_NONE, ALERT_WARN, ALERT_CRIT

log = logging.getLogger("tbank.data")


class DataStore:
    """
    Хранит все данные приложения и обновляет их в фоне.
    Потокобезопасен: все поля защищены _lock.
    menu.py берёт снапшот через snapshot() и работает с копией.
    """

    def __init__(self, apis: list, cfg: dict):
        # apis: list of (connection_name: str, api_instance)
        self._apis = apis
        self._cfg  = cfg
        self._lock = threading.Lock()

        # ── Данные портфеля
        self.portfolios:       list[dict] = []
        self.positions_extra:  list[dict] = []  # для аллокации и топ-муверов
        self.bond_positions:   dict       = {}   # figi → {name,isin,qty}
        self.bond_nkd:         dict       = {}   # figi → {nkd_per,nkd_total,qty,name,isin}
        self.bond_events:      list[dict] = []   # отсортированы по дате
        self.bond_analytics:   list[dict] = []   # для YTM

        # ── Статус
        self.last_update:      str              = "—"
        self.last_bond_update: datetime | None  = None
        self.error:            str | None       = None
        self.dismissed:        set              = load_dismissed()

        # ── Настройки меню
        self.show_mode:        str  = "day"      # "day" | "alltime"
        self.bond_horizon:     int  = cfg.get("bond_horizon_days", 60)
        self.bond_sort:        str  = cfg.get("bond_sort", "date")  # "date" | "amount"
        self.alert_level:      int  = ALERT_NONE

        # ── История портфеля
        self.portfolio_history: list[dict] = load_history()
        self._last_history_ts: float = 0

        # ── Кэш данных инструментов (figi → {isin, name, ticker, logo_url})
        self._instrument_cache: dict = {}

        # ── Информация об обновлении
        self.update_info: dict = {}

        # Загружаем кэш при старте для мгновенного отображения
        self._load_from_cache()

    # ──────────────────────────────────────────
    #  Кэш
    # ──────────────────────────────────────────
    def _load_from_cache(self):
        data = load_cache()
        if not data:
            return
        with self._lock:
            self.portfolios      = data.get("portfolios", [])
            self.bond_events     = data.get("bond_events", [])
            self.bond_nkd        = data.get("bond_nkd", {})
            self.positions_extra = data.get("positions_extra", [])
            self.bond_analytics  = data.get("bond_analytics", [])
            self.last_update     = "из кэша"
        log.info("Данные загружены из кэша")

    def save_to_cache(self):
        with self._lock:
            p   = list(self.portfolios)
            be  = list(self.bond_events)
            bn  = dict(self.bond_nkd)
            pe  = list(self.positions_extra)
            ba  = list(self.bond_analytics)
            ph  = list(self.portfolio_history)
        save_cache(p, be, bn, pe, ba)
        save_history(ph)

    # ──────────────────────────────────────────
    #  Снапшот для menu.py (не держим lock)
    # ──────────────────────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "portfolios":      list(self.portfolios),
                "bond_events":     list(self.bond_events),
                "bond_nkd":        dict(self.bond_nkd),
                "positions_extra": list(self.positions_extra),
                "bond_analytics":  list(self.bond_analytics),
                "last_update":     self.last_update,
                "error":           self.error,
                "show_mode":       self.show_mode,
                "bond_horizon":    self.bond_horizon,
                "bond_sort":       self.bond_sort,
                "alert_level":     self.alert_level,
                "dismissed":       set(self.dismissed),
                "portfolio_history": list(self.portfolio_history),
                "update_info":       dict(self.update_info) if self.update_info else {},
            }

    # ──────────────────────────────────────────
    #  Загрузка портфеля
    # ──────────────────────────────────────────
    def fetch_portfolio(self):
        result        = []
        bond_pos      = {}
        bond_nkd      = {}
        positions_all = []
        errors        = []

        for conn_name, api in self._apis:
            try:
                accounts = api.get_accounts()

                for acc in accounts:
                    acc_id   = acc.get("id", "")
                    acc_name = acc.get("name") or acc.get("type", "Счёт")
                    p        = api.get_portfolio(acc_id)

                    total         = money_value(p.get("totalAmountPortfolio"))
                    day_delta     = money_value(p.get("dailyYield"))
                    alltime_delta = 0.0

                    for pos in p.get("positions", []):
                        itype  = pos.get("instrumentType", "").lower()
                        figi   = pos.get("figi", "")
                        isin   = pos.get("isin", "")
                        name   = pos.get("name") or isin or figi
                        ticker = pos.get("ticker", "")
                        qty_raw = money_value(pos.get("quantity"))
                        qty     = qty_raw if itype == "currency" else int(qty_raw)
                        cur_p   = money_value(pos.get("currentPrice"))
                        nkd     = money_value(pos.get("currentNkd"))
                        pos_pnl = money_value(pos.get("expectedYield"))
                        pos_day = money_value(pos.get("dailyYield"))

                        pos_value = cur_p * qty if cur_p else 0
                        alltime_delta += pos_pnl

                        positions_all.append({
                            "instrumentType":  itype,
                            "name":            name,
                            "isin":            isin,
                            "figi":            figi,
                            "ticker":          ticker,
                            "qty":             qty,
                            "current_price":   cur_p,
                            "current_value":   pos_value,
                            "day_delta":       pos_day,
                            "alltime_delta":   pos_pnl,
                            "account_id":      acc_id,
                            "account_name":    acc_name,
                            "connection_name": conn_name,
                            "logo_url":        "",
                        })

                        if itype == "bond" and figi and qty > 0:
                            if figi in bond_pos:
                                bond_pos[figi]["qty"]       += qty
                                bond_nkd[figi]["qty"]       += qty
                                bond_nkd[figi]["nkd_total"] += nkd * qty
                            else:
                                bond_pos[figi] = {"name": name, "isin": isin, "qty": qty}
                                bond_nkd[figi] = {
                                    "name":      name,
                                    "isin":      isin,
                                    "nkd_per":   nkd,
                                    "nkd_total": nkd * qty,
                                    "qty":       qty,
                                }

                    result.append({
                        "name":            acc_name,
                        "total":           total,
                        "day_delta":       day_delta,
                        "alltime_delta":   alltime_delta,
                        "account_id":      acc_id,
                        "connection_name": conn_name,
                    })

                # Быстрое обогащение из кэша (без API-запросов)
                for pos in positions_all:
                    figi = pos.get("figi", "")
                    cached = self._instrument_cache.get(figi) if figi else None
                    if cached:
                        if not pos["isin"]:
                            pos["isin"] = cached.get("isin", "")
                        if not pos.get("ticker"):
                            pos["ticker"] = cached.get("ticker", "")
                        if pos["name"] == figi:
                            pos["name"] = cached.get("name", figi)
                        if cached.get("logo_url"):
                            pos["logo_url"] = cached["logo_url"]

            except TBankAPIError as e:
                errors.append(f"[{conn_name}] {str(e)[:60]}")
                log.error("fetch_portfolio [%s]: %s", conn_name, e)
            except Exception as e:
                errors.append(f"[{conn_name}] {str(e)[:60]}")
                log.exception("fetch_portfolio [%s] unexpected:", conn_name)

        with self._lock:
            self.portfolios      = result
            self.bond_positions  = bond_pos
            self.bond_nkd        = bond_nkd
            self.positions_extra = positions_all
            self.last_update     = datetime.now().strftime("%H:%M:%S")
            self.error           = "; ".join(errors) if errors and not result else None

            # Записываем точку истории (раз в 5 минут)
            total_val = sum(p["total"] for p in result)
            now_ts = _time.time()
            if total_val > 0 and now_ts - self._last_history_ts >= 300:
                self.portfolio_history.append({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "value": total_val,
                })
                self._last_history_ts = now_ts

        # Фоновое обогащение (ISIN, имена, логотипы) — после сохранения данных
        self._enrich_positions()

    def _enrich_positions(self):
        """Обогащает позиции данными инструментов (ISIN, тикер, логотип).
        Вызывается ПОСЛЕ сохранения портфеля, не блокирует отображение."""
        with self._lock:
            positions = list(self.positions_extra)

        changed = False
        for pos in positions:
            figi = pos.get("figi", "")
            if not figi or figi in self._instrument_cache:
                continue
            needs = not pos.get("isin") or pos.get("name") == figi or self._cfg.get("use_logos")
            if not needs:
                continue

            _time.sleep(0.2)
            # Берём первый API из списка
            if not self._apis:
                break
            _, api = self._apis[0]

            itype = pos.get("instrumentType", "")
            info = None
            try:
                if itype == "bond":
                    info = api.get_bond_by_figi(figi)
                if not info:
                    info = api.get_instrument_by_figi(figi)
            except Exception:
                continue
            if not info:
                continue

            if not pos.get("isin"):
                pos["isin"] = info.get("isin", "")
            if not pos.get("ticker"):
                pos["ticker"] = info.get("ticker", "")
            if pos.get("name") == figi:
                pos["name"] = info.get("name", figi)
            logo_url = ""
            brand = info.get("brand", {})
            logo = brand.get("logoName", "") if brand else ""
            if logo:
                logo_id = logo.replace(".png", "").replace(".jpg", "")
                logo_url = LOGO_CDN.format(logo_id=logo_id)
                pos["logo_url"] = logo_url

            self._instrument_cache[figi] = {
                "isin": pos.get("isin", ""), "name": pos.get("name", ""),
                "ticker": pos.get("ticker", ""), "logo_url": logo_url,
            }
            changed = True

        if changed:
            with self._lock:
                self.positions_extra = positions

    # ──────────────────────────────────────────
    #  Загрузка событий облигаций
    # ──────────────────────────────────────────
    def fetch_bond_events(self):
        with self._lock:
            bond_pos = dict(self.bond_positions)
            bond_nkd = dict(self.bond_nkd)
            horizon  = self.bond_horizon

        if not bond_pos:
            return

        now = datetime.now(timezone.utc)
        # Начало текущего дня (чтобы не пропустить сегодняшние купоны)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        horizon_dt = now + timedelta(days=horizon)
        events: list[dict] = []
        analytics: list[dict] = []

        for i, (figi, info) in enumerate(bond_pos.items()):
            name = info["name"]
            qty  = info["qty"]
            isin = info.get("isin", "")
            nkd_per = bond_nkd.get(figi, {}).get("nkd_per", 0)

            # Пауза между запросами (rate limit)
            if i > 0:
                _time.sleep(0.3)

            api = self._apis[0][1]

            # Сначала проверяем кэш инструментов
            cached = self._instrument_cache.get(figi)
            bond = api.get_bond_by_figi(figi)
            if bond:
                # Всегда берём настоящее имя и ticker из API
                real_name = bond.get("name") or name
                bond_ticker = bond.get("ticker", "")
                isin = bond.get("isin", "") or isin

                # Сохраняем в кэш
                logo_url = ""
                brand = bond.get("brand", {})
                logo = brand.get("logoName", "") if brand else ""
                if logo:
                    logo_id = logo.replace(".png", "").replace(".jpg", "")
                    logo_url = LOGO_CDN.format(logo_id=logo_id)
                self._instrument_cache[figi] = {
                    "isin": isin, "name": real_name,
                    "ticker": bond_ticker, "logo_url": logo_url,
                }
                name = real_name

                # Для YTM
                face_val = money_value(bond.get("nominal"))
                mat_ts   = parse_ts(bond.get("maturityDate"))
                ann_coupon = money_value(bond.get("initialNominal")) * \
                             float(bond.get("couponQuantityPerYear", 0) or 0) * \
                             money_value(bond.get("couponRate"))

                nkd_data = bond_nkd.get(figi, {})
                cur_price = nkd_data.get("nkd_per", 0)

                analytics.append({
                    "name":           name,
                    "figi":           figi,
                    "isin":           isin,
                    "ticker":         bond_ticker,
                    "qty":            qty,
                    "face_value":     face_val or 1000,
                    "maturity_date":  mat_ts,
                    "annual_coupon":  ann_coupon,
                    "current_price":  cur_price,
                })
            elif cached:
                # Данные из кэша если API не ответил
                name = cached.get("name", name)
                bond_ticker = cached.get("ticker", "")
                isin = cached.get("isin", isin)
            else:
                bond_ticker = ""

            if bond:
                for ev_type, field in [("maturity", "maturityDate"),
                                       ("offer",    "putDate"),
                                       ("call",     "callDate")]:
                    dt = parse_ts(bond.get(field))
                    if dt and now < dt <= horizon_dt:
                        events.append({
                            "type": ev_type, "name": name,
                            "isin": isin, "figi": figi,
                            "ticker": bond_ticker,
                            "date": dt, "amount": None,
                            "amount_est": None, "qty": qty,
                        })

            # Купоны
            _time.sleep(0.2)
            for c in api.get_bond_coupons(figi, today_start, horizon_dt):
                dt     = parse_ts(c.get("couponDate"))
                amount = money_value(c.get("payOneBond"))
                if dt and dt.date() >= now.date():
                    # Если сумма купона неизвестна — оцениваем через НКД
                    amount_est = None
                    is_est     = False
                    if not amount and nkd_per > 0:
                        amount_est = nkd_per
                        is_est     = True
                    events.append({
                        "type":       "coupon",
                        "name":       name,
                        "isin":       isin,
                        "figi":       figi,
                        "ticker":     bond_ticker,
                        "date":       dt,
                        "amount":     amount if not is_est else None,
                        "amount_est": amount_est,
                        "qty":        qty,
                    })

        # ── Дивиденды по акциям ──────────────────────────
        with self._lock:
            share_positions = [p for p in self.positions_extra
                               if p.get("instrumentType") == "share" and p.get("figi")]

        seen_shares = set()
        for pos in share_positions:
            figi = pos["figi"]
            if figi in seen_shares:
                continue
            seen_shares.add(figi)
            _time.sleep(0.2)
            # Берём API из первого подключения
            if not self._apis:
                break
            _, api = self._apis[0]
            try:
                divs = api.get_dividends(figi, today_start, horizon_dt)
                for d in divs:
                    dt = parse_ts(d.get("paymentDate"))
                    if not dt:
                        dt = parse_ts(d.get("recordDate"))
                    if dt and dt.date() >= now.date():
                        amount = money_value(d.get("dividendNet"))
                        events.append({
                            "type":       "dividend",
                            "name":       pos.get("name", figi),
                            "isin":       pos.get("isin", ""),
                            "figi":       figi,
                            "ticker":     pos.get("ticker", ""),
                            "date":       dt,
                            "amount":     amount,
                            "amount_est": None,
                            "qty":        pos.get("qty", 0),
                        })
            except Exception as e:
                log.debug("get_dividends(%s): %s", figi, e)

        events.sort(key=lambda e: e["date"])

        with self._lock:
            self.bond_events      = events
            self.bond_analytics   = analytics
            self.last_bond_update = datetime.now(timezone.utc)
            # Обновляем ISIN и имена в bond_positions и positions_extra
            # (GetPortfolio не возвращает ISIN/name, BondBy — возвращает)
            isin_map = {}  # figi → {isin, name}
            for a in analytics:
                if a["figi"] and a["isin"]:
                    isin_map[a["figi"]] = {"isin": a["isin"], "name": a["name"]}
                if a["figi"] in self.bond_positions and a["isin"]:
                    self.bond_positions[a["figi"]]["isin"] = a["isin"]

            for pos in self.positions_extra:
                info = isin_map.get(pos.get("figi"))
                if info:
                    if not pos["isin"]:
                        pos["isin"] = info["isin"]
                    if pos["name"] == pos["figi"]:
                        pos["name"] = info["name"]

    # ──────────────────────────────────────────
    #  Уровень алерта
    # ──────────────────────────────────────────
    def compute_alert(self) -> int:
        with self._lock:
            events    = list(self.bond_events)
            dismissed = set(self.dismissed)
            warn_days = self._cfg.get("notify_offer_days", 2)

        level = ALERT_NONE
        for e in events:
            if e["type"] not in ("offer", "call"):
                continue
            d   = days_until(e["date"])
            key = alert_key(e)
            if d == 0:
                return ALERT_CRIT
            if d <= warn_days and key not in dismissed:
                level = ALERT_WARN
        return level

    # ──────────────────────────────────────────
    #  Действия пользователя
    # ──────────────────────────────────────────
    def toggle_mode(self):
        with self._lock:
            self.show_mode = "alltime" if self.show_mode == "day" else "day"

    def set_horizon(self, days: int, cfg: dict):
        with self._lock:
            self.bond_horizon = days
        cfg["bond_horizon_days"] = days
        from core.config import save_config
        save_config(cfg)
        # Сбрасываем дату обновления чтобы перезагрузить события
        with self._lock:
            self.last_bond_update = None

    def toggle_bond_sort(self, cfg: dict):
        with self._lock:
            self.bond_sort = "amount" if self.bond_sort == "date" else "date"
            new_sort = self.bond_sort
        cfg["bond_sort"] = new_sort
        from core.config import save_config
        save_config(cfg)

    def dismiss_warnings(self):
        with self._lock:
            events    = list(self.bond_events)
            dismissed = self.dismissed
            warn_days = self._cfg.get("notify_offer_days", 2)
        for e in events:
            if e["type"] in ("offer", "call"):
                d = days_until(e["date"])
                if 1 <= d <= warn_days:
                    dismissed.add(alert_key(e))
        with self._lock:
            self.dismissed = dismissed
        save_dismissed(dismissed)
