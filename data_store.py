"""
data_store.py — загрузка данных из API и хранение в памяти.
Вся работа с API происходит здесь; menu.py только читает.
"""
import logging
import threading
from datetime import datetime, timezone, timedelta

from api import TBankAPI, TBankAPIError
from utils import money_value, parse_ts, days_until, alert_key
import time as _time
from cache import save_cache, load_cache, save_history, load_history
from config import load_dismissed, save_dismissed

log = logging.getLogger("tbank.data")

ALERT_NONE = 0
ALERT_WARN = 1
ALERT_CRIT = 2


class DataStore:
    """
    Хранит все данные приложения и обновляет их в фоне.
    Потокобезопасен: все поля защищены _lock.
    menu.py берёт снапшот через snapshot() и работает с копией.
    """

    def __init__(self, api: TBankAPI, cfg: dict):
        self._api = api
        self._cfg = cfg
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
            self.last_update     = "из кэша"
        log.info("Данные загружены из кэша")

    def save_to_cache(self):
        with self._lock:
            p   = list(self.portfolios)
            be  = list(self.bond_events)
            bn  = dict(self.bond_nkd)
            pe  = list(self.positions_extra)
            ph  = list(self.portfolio_history)
        save_cache(p, be, bn, pe)
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
            }

    # ──────────────────────────────────────────
    #  Загрузка портфеля
    # ──────────────────────────────────────────
    def fetch_portfolio(self):
        try:
            accounts = self._api.get_accounts()
            result        = []
            bond_pos      = {}
            bond_nkd      = {}
            positions_all = []

            for acc in accounts:
                acc_id   = acc.get("id", "")
                acc_name = acc.get("name") or acc.get("type", "Счёт")
                p        = self._api.get_portfolio(acc_id)

                total         = money_value(p.get("totalAmountPortfolio"))
                day_delta     = money_value(p.get("dailyYield"))
                # expectedYield портфеля — это % доходности, не рубли!
                # alltime_delta считаем как сумму expectedYield всех позиций
                alltime_delta = 0.0

                for pos in p.get("positions", []):
                    itype = pos.get("instrumentType", "").lower()
                    figi  = pos.get("figi", "")
                    isin  = pos.get("isin", "")
                    name  = pos.get("name") or isin or figi
                    ticker = pos.get("ticker", "")
                    qty   = int(float((pos.get("quantity") or {}).get("units", 0)))
                    cur_p = money_value(pos.get("currentPrice"))
                    nkd   = money_value(pos.get("currentNkd"))
                    pos_pnl  = money_value(pos.get("expectedYield"))   # P&L за всё время (руб)
                    pos_day  = money_value(pos.get("dailyYield"))      # P&L за сегодня (руб)

                    # текущая стоимость позиции = цена × кол-во
                    pos_value = cur_p * qty if cur_p else 0
                    alltime_delta += pos_pnl

                    positions_all.append({
                        "instrumentType": itype,
                        "name":           name,
                        "isin":           isin,
                        "figi":           figi,
                        "ticker":         ticker,
                        "qty":            qty,
                        "current_price":  cur_p,
                        "current_value":  pos_value,
                        "day_delta":      pos_day,
                        "alltime_delta":  pos_pnl,
                        "account_id":     acc_id,
                        "account_name":   acc_name,
                        "logo_url":       "",
                    })

                    if itype == "bond" and figi and qty > 0:
                        if figi in bond_pos:
                            bond_pos[figi]["qty"]           += qty
                            bond_nkd[figi]["qty"]           += qty
                            bond_nkd[figi]["nkd_total"]     += nkd * qty
                        else:
                            bond_pos[figi] = {
                                "name": name, "isin": isin, "qty": qty,
                            }
                            bond_nkd[figi] = {
                                "name":      name,
                                "isin":      isin,
                                "nkd_per":   nkd,
                                "nkd_total": nkd * qty,
                                "qty":       qty,
                            }

                result.append({
                    "name":          acc_name,
                    "total":         total,
                    "day_delta":     day_delta,
                    "alltime_delta": alltime_delta,
                    "account_id":    acc_id,
                })

            # Обогащаем позиции: подтягиваем ISIN, имя и логотип
            # (ticker уже приходит из GetPortfolio)
            # Используем кэш чтобы не делать лишних запросов (429 rate limit)
            for pos in positions_all:
                figi = pos.get("figi", "")
                if not figi:
                    continue

                # Проверяем кэш
                cached = self._instrument_cache.get(figi)
                if cached:
                    if not pos["isin"]:
                        pos["isin"] = cached.get("isin", "")
                    if not pos.get("ticker"):
                        pos["ticker"] = cached.get("ticker", "")
                    if pos["name"] == figi:
                        pos["name"] = cached.get("name", figi)
                    if cached.get("logo_url"):
                        pos["logo_url"] = cached["logo_url"]
                    continue

                # Нужен ли запрос к API?
                needs = not pos["isin"] or pos["name"] == figi or self._cfg.get("use_logos")
                if not needs:
                    continue

                # Запрос к API с паузой (rate limit)
                _time.sleep(0.2)
                itype = pos.get("instrumentType", "")
                info = None
                if itype == "bond":
                    info = self._api.get_bond_by_figi(figi)
                if not info:
                    info = self._api.get_instrument_by_figi(figi)
                if not info:
                    continue

                if not pos["isin"]:
                    pos["isin"] = info.get("isin", "")
                if not pos.get("ticker"):
                    pos["ticker"] = info.get("ticker", "")
                if pos["name"] == figi:
                    pos["name"] = info.get("name", figi)
                logo_url = ""
                brand = info.get("brand", {})
                logo = brand.get("logoName", "") if brand else ""
                if logo:
                    logo_id = logo.replace(".png", "").replace(".jpg", "")
                    logo_url = f"https://invest-brands.cdn-tinkoff.ru/{logo_id}x160.png"
                    pos["logo_url"] = logo_url

                # Сохраняем в кэш
                self._instrument_cache[figi] = {
                    "isin": pos["isin"], "name": pos["name"],
                    "ticker": pos.get("ticker", ""),
                    "logo_url": logo_url,
                }

            with self._lock:
                self.portfolios      = result
                self.bond_positions  = bond_pos
                self.bond_nkd        = bond_nkd
                self.positions_extra = positions_all
                self.last_update     = datetime.now().strftime("%H:%M:%S")
                self.error           = None

                # Записываем точку истории (раз в 5 минут)
                total = sum(p["total"] for p in result)
                now_ts = _time.time()
                if total > 0 and now_ts - self._last_history_ts >= 300:
                    self.portfolio_history.append({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "value": total,
                    })
                    self._last_history_ts = now_ts

        except TBankAPIError as e:
            with self._lock:
                self.error = str(e)[:80]
            log.error("fetch_portfolio: %s", e)
        except Exception as e:
            with self._lock:
                self.error = str(e)[:80]
            log.exception("fetch_portfolio unexpected:")

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

        now     = datetime.now(timezone.utc)
        horizon_dt = now + timedelta(days=horizon)
        events: list[dict] = []
        analytics: list[dict] = []

        for figi, info in bond_pos.items():
            name = info["name"]
            qty  = info["qty"]
            isin = info.get("isin", "")
            nkd_per = bond_nkd.get(figi, {}).get("nkd_per", 0)

            bond = self._api.get_bond_by_figi(figi)
            if bond:
                if not isin:
                    isin = bond.get("isin", "")

                # Для YTM
                face_val = money_value(bond.get("nominal"))
                mat_ts   = parse_ts(bond.get("maturityDate"))
                ann_coupon = money_value(bond.get("initialNominal")) * \
                             float(bond.get("couponQuantityPerYear", 0) or 0) * \
                             money_value(bond.get("couponRate"))   # приближение

                nkd_data = bond_nkd.get(figi, {})
                cur_price = nkd_data.get("nkd_per", 0)   # НКД как прокси цены — заменить на реальную

                analytics.append({
                    "name":           name,
                    "figi":           figi,
                    "isin":           isin,
                    "qty":            qty,
                    "face_value":     face_val or 1000,
                    "maturity_date":  mat_ts,
                    "annual_coupon":  ann_coupon,
                    "current_price":  cur_price,
                })

                for ev_type, field in [("maturity", "maturityDate"),
                                       ("offer",    "putDate"),
                                       ("call",     "callDate")]:
                    dt = parse_ts(bond.get(field))
                    if dt and now < dt <= horizon_dt:
                        events.append({
                            "type": ev_type, "name": name,
                            "isin": isin, "figi": figi,
                            "date": dt, "amount": None,
                            "amount_est": None, "qty": qty,
                        })

            # Купоны
            for c in self._api.get_bond_coupons(figi, now, horizon_dt):
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
                        "date":       dt,
                        "amount":     amount if not is_est else None,
                        "amount_est": amount_est,  # расчётное значение
                        "qty":        qty,
                    })

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
        from config import save_config
        save_config(cfg)
        # Сбрасываем дату обновления чтобы перезагрузить события
        with self._lock:
            self.last_bond_update = None

    def toggle_bond_sort(self, cfg: dict):
        with self._lock:
            self.bond_sort = "amount" if self.bond_sort == "date" else "date"
            new_sort = self.bond_sort
        cfg["bond_sort"] = new_sort
        from config import save_config
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
