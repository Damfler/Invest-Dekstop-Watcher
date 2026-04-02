"""
utils.py — общие вспомогательные функции
"""
from datetime import datetime, timezone


def money_value(obj: dict | None) -> float:
    if not obj:
        return 0.0
    return int(obj.get("units", 0)) + int(obj.get("nano", 0)) / 1_000_000_000


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def days_until(dt: datetime) -> int:
    today = datetime.now().date()
    event_date = dt.date() if dt.tzinfo is None else dt.astimezone().date()
    return (event_date - today).days


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


def fmt_money(v: float) -> str:
    return f"{v:,.2f} ₽".replace(",", " ")


def fmt_total(v: float) -> str:
    return f"{v:,.0f} ₽".replace(",", " ")


def fmt_delta(v: float) -> str:
    return f"{'+'if v >= 0 else ''}{v:,.0f} ₽".replace(",", " ")


def fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def fmt_days(n: int) -> str:
    if n == 0: return "❗ СЕГОДНЯ"
    if n == 1: return "⚠ завтра"
    if n == 2: return "⚠ послезавтра"
    return f"через {n} дн."


def alert_key(event: dict) -> str:
    return f"{event['isin']}_{event['date'].date()}"
