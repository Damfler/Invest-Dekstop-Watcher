"""
analytics.py — аналитические расчёты поверх данных портфеля
"""
from datetime import datetime, timezone, timedelta
from utils import days_until, fmt_pct


# ──────────────────────────────────────────────────────────
#  YTM — упрощённая доходность к погашению
# ──────────────────────────────────────────────────────────

def calc_ytm_simple(coupon_per_year: float, current_price: float,
                    face_value: float, years_to_maturity: float) -> float | None:
    """
    Приближённый YTM:
        YTM ≈ (C + (F - P) / N) / ((F + P) / 2)
    C = годовой купон, F = номинал, P = текущая цена, N = лет до погашения.
    Возвращает None если данных недостаточно.
    """
    if years_to_maturity <= 0 or current_price <= 0 or face_value <= 0:
        return None
    try:
        ytm = (coupon_per_year + (face_value - current_price) / years_to_maturity) / \
              ((face_value + current_price) / 2)
        return round(ytm * 100, 2)   # в процентах
    except ZeroDivisionError:
        return None


def compute_portfolio_ytm(bond_positions: list[dict]) -> float | None:
    """
    Взвешенный YTM по всем облигациям в портфеле.
    bond_positions: [{ name, figi, isin, qty, current_price,
                       face_value, maturity_date, annual_coupon }]
    """
    total_weight = 0.0
    weighted_ytm = 0.0
    now = datetime.now(timezone.utc)

    for pos in bond_positions:
        mat  = pos.get("maturity_date")
        if not mat:
            continue
        if isinstance(mat, str):
            from utils import parse_ts
            mat = parse_ts(mat)
        if not mat:
            continue

        years = (mat - now).days / 365.25
        ytm   = calc_ytm_simple(
            coupon_per_year  = pos.get("annual_coupon", 0),
            current_price    = pos.get("current_price", 0),
            face_value       = pos.get("face_value", 1000),
            years_to_maturity = years,
        )
        if ytm is None:
            continue

        weight        = pos.get("qty", 1) * pos.get("current_price", 1)
        total_weight += weight
        weighted_ytm += ytm * weight

    if total_weight <= 0:
        return None
    return round(weighted_ytm / total_weight, 2)


# ──────────────────────────────────────────────────────────
#  Аллокация портфеля
# ──────────────────────────────────────────────────────────

_TYPE_MAP = {
    "bond":     "Облигации",
    "share":    "Акции",
    "etf":      "Фонды",
    "currency": "Валюта",
    "futures":  "Фьючерсы",
    "option":   "Опционы",
    "sp":       "Структурные",
}


def compute_allocation(positions: list[dict]) -> list[tuple[str, float]]:
    """
    positions: [{ instrumentType, current_value }]
    Возвращает [(label, pct), ...] отсортировано по убыванию.
    """
    totals: dict[str, float] = {}
    grand = 0.0

    for pos in positions:
        itype = pos.get("instrumentType", "").lower()
        val   = float(pos.get("current_value", 0) or 0)
        label = _TYPE_MAP.get(itype, itype.capitalize() or "Прочее")
        totals[label] = totals.get(label, 0) + val
        grand += val

    if grand <= 0:
        return []

    result = [(lbl, round(v / grand * 100, 1)) for lbl, v in totals.items()]
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def fmt_allocation(alloc: list[tuple[str, float]]) -> str:
    """Одна строка: 'Акции 45% · Облигации 38% · Фонды 12%'"""
    if not alloc:
        return ""
    parts = [f"{lbl} {fmt_pct(pct)}" for lbl, pct in alloc if pct >= 1.0]
    return " · ".join(parts)


# ──────────────────────────────────────────────────────────
#  Топ-3 муверы
# ──────────────────────────────────────────────────────────

def top_movers(positions: list[dict], n: int = 3) -> tuple[list, list]:
    """
    positions: [{ name, isin, day_delta, current_value }]
    Возвращает (top_gainers, top_losers) — каждый список по n элементов.
    Фильтруем позиции без day_delta.
    """
    valid = [p for p in positions if p.get("day_delta") is not None]
    valid.sort(key=lambda p: p.get("day_delta", 0), reverse=True)
    gainers = [p for p in valid if p.get("day_delta", 0) > 0][:n]
    losers  = list(reversed([p for p in valid if p.get("day_delta", 0) < 0]))[:n]
    return gainers, losers


# ──────────────────────────────────────────────────────────
#  Денежный поток по месяцам
# ──────────────────────────────────────────────────────────

def monthly_coupon_flow(bond_events: list[dict],
                        months: int = 12) -> list[tuple[str, float]]:
    """
    Суммирует купонные выплаты по каждому из ближайших N месяцев.
    Возвращает [(label, sum), ...] — label = "Апр 25".
    """
    now    = datetime.now(timezone.utc)
    buckets: dict[tuple, float] = {}

    for e in bond_events:
        if e["type"] != "coupon":
            continue
        dt = e["date"]
        if dt is None:
            continue
        dt_utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if dt_utc <= now:
            continue
        key = (dt_utc.year, dt_utc.month)
        amount = e.get("amount") or e.get("amount_est") or 0
        buckets[key] = buckets.get(key, 0) + amount * e["qty"]

    result = []
    for i in range(months):
        d   = now + timedelta(days=30 * i)
        key = (d.year, d.month)
        lbl = d.strftime("%b %y").capitalize()
        result.append((lbl, round(buckets.get(key, 0), 2)))

    return result


# ──────────────────────────────────────────────────────────
#  Суммарные купоны за горизонт
# ──────────────────────────────────────────────────────────

def coupon_sum_horizon(bond_events: list[dict], days: int) -> float:
    now     = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)
    total   = 0.0
    for e in bond_events:
        if e["type"] != "coupon":
            continue
        dt = e["date"]
        if dt is None:
            continue
        dt_utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if now < dt_utc <= horizon:
            amount = e.get("amount") or e.get("amount_est") or 0
            total += amount * e["qty"]
    return total
