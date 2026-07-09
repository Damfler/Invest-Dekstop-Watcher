"""
moex_iss.py — простой клиент MOEX ISS для купонов/дивидендов.

Нужен, чтобы довести функционал БКС до уровня T‑Bank по календарю выплат:
BCS Trade API в текущем виде не отдаёт купоны/дивиденды отдельными методами.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import requests

log = logging.getLogger("stack.moex")

_BASE = "https://iss.moex.com/iss"


def _to_ymd(dt: datetime) -> str:
    return dt.date().isoformat()


def _flatten(block: dict) -> list[dict]:
    cols = block.get("columns") or []
    data = block.get("data") or []
    out: list[dict] = []
    for row in data:
        if not isinstance(row, list):
            continue
        out.append({cols[i]: row[i] if i < len(row) else None for i in range(len(cols))})
    return out


def _get(path: str, *, params: dict | None = None) -> dict:
    url = f"{_BASE}/{path.lstrip('/')}"
    r = requests.get(url, params=params or {}, timeout=25)
    r.raise_for_status()
    return r.json()


def bond_coupons(secid: str, *, from_dt: datetime, to_dt: datetime) -> list[dict]:
    """
    Возвращает список купонов в стиле T‑Bank Invest API:
      [{"couponDate": "...", "payOneBond": {"units":..,"nano":..}}, ...]
    """
    secid = (secid or "").strip().upper()
    if not secid:
        return []
    try:
        j = _get(
            f"statistics/engines/stock/markets/bonds/bondization/{secid}.json",
            params={
                "from": _to_ymd(from_dt),
                "till": _to_ymd(to_dt),
                "iss.meta": "off",
                "iss.only": "coupons,amortizations",
            },
        )
    except Exception as e:
        log.debug("bond_coupons(%s): %s", secid, e)
        return []

    coupons = _flatten(j.get("coupons") or {})
    out: list[dict] = []
    for c in coupons:
        dt = c.get("COUPONDATE") or c.get("coupondate")
        val = c.get("VALUE") or c.get("value")
        if not dt or not val:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        units = int(v)
        nano = int(round((v - units) * 1_000_000_000))
        out.append({"couponDate": f"{dt}T00:00:00Z", "payOneBond": {"units": units, "nano": nano}})

    # amortizations — добавим как отдельные выплаты (погашение части номинала)
    ams = _flatten(j.get("amortizations") or {})
    for a in ams:
        dt = a.get("AMORTDATE") or a.get("amortdate") or a.get("PAYDATE") or a.get("paydate")
        val = a.get("VALUE") or a.get("value")
        if not dt or not val:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        units = int(v)
        nano = int(round((v - units) * 1_000_000_000))
        out.append({"couponDate": f"{dt}T00:00:00Z", "payOneBond": {"units": units, "nano": nano}})

    out.sort(key=lambda x: x.get("couponDate") or "")
    return out


def dividends(secid: str, *, from_dt: datetime, to_dt: datetime) -> list[dict]:
    """
    Возвращает список дивидендов в стиле T‑Bank Invest API:
      [{"paymentDate": "...", "dividendNet": {"units":..,"nano":..}}, ...]
    """
    secid = (secid or "").strip().upper()
    if not secid:
        return []
    try:
        j = _get(
            f"securities/{secid}/dividends.json",
            params={"iss.meta": "off"},
        )
    except Exception as e:
        log.debug("dividends(%s): %s", secid, e)
        return []

    rows = _flatten(j.get("dividends") or {})
    d0 = from_dt.date()
    d1 = to_dt.date()
    out: list[dict] = []
    for r in rows:
        # MOEX: RegistryCloseDate / PaymentDate / Value
        pay = r.get("PAYMENTDATE") or r.get("paymentdate") or r.get("REGISTERCLOSEDATE") or r.get("registryclosedate")
        val = r.get("VALUE") or r.get("value")
        if not pay or not val:
            continue
        try:
            pdate = date.fromisoformat(str(pay)[:10])
        except Exception:
            continue
        if pdate < d0 or pdate > d1:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        units = int(v)
        nano = int(round((v - units) * 1_000_000_000))
        out.append({"paymentDate": f"{pdate.isoformat()}T00:00:00Z", "dividendNet": {"units": units, "nano": nano}})

    out.sort(key=lambda x: x.get("paymentDate") or "")
    return out


def bond_static(secid: str) -> dict | None:
    """
    Статические поля облигации с MOEX ISS (maturity/offer/buyback, nominal, coupon).
    Возвращает dict с ключами в стиле T‑Bank (частично).
    """
    secid = (secid or "").strip().upper()
    if not secid:
        return None
    # Самый стабильный источник — /iss/securities/{SECID}.json → description (key/value).
    try:
        j = _get(f"securities/{secid}.json", params={"iss.meta": "off"})
    except Exception as e:
        log.debug("bond_static(%s): %s", secid, e)
        return None

    desc_rows = _flatten(j.get("description") or {})
    if not desc_rows:
        return None
    r = {str(x.get("name") or "").upper(): x.get("value") for x in desc_rows if isinstance(x, dict)}

    def _d(key: str) -> str:
        v = r.get(key.upper())
        if not v:
            return ""
        # ожидаем YYYY-MM-DD
        s = str(v)[:10]
        return f"{s}T00:00:00Z"

    info: dict = {
        "ticker": secid,
        "name": r.get("SHORTNAME") or r.get("SECNAME") or secid,
        "isin": r.get("ISIN") or "",
        "maturityDate": _d("MATDATE") or None,
        "putDate": _d("OFFERDATE") or None,
        # BUYBACKDATE ближе к call/buyback; используем как callDate для событий
        "callDate": _d("BUYBACKDATE") or None,
    }

    try:
        fv = float(r.get("FACEVALUE") or r.get("INITIALFACEVALUE") or 0)
    except (TypeError, ValueError):
        fv = 0.0
    if fv:
        units = int(fv)
        nano = int(round((fv - units) * 1_000_000_000))
        info["nominal"] = {"units": units, "nano": nano}

    try:
        cv = float(r.get("COUPONVALUE") or 0)
    except (TypeError, ValueError):
        cv = 0.0
    if cv:
        units = int(cv)
        nano = int(round((cv - units) * 1_000_000_000))
        info["coupon"] = {"units": units, "nano": nano}

    try:
        cp = float(r.get("COUPONPERCENT") or 0)
    except (TypeError, ValueError):
        cp = 0.0
    if cp:
        info["couponRate"] = cp  # проценты годовых

    try:
        period_days = float(r.get("COUPONPERIOD") or 0)
    except (TypeError, ValueError):
        period_days = 0.0
    if period_days > 0:
        info["couponQuantityPerYear"] = max(1.0, 365.0 / period_days)

    return info

