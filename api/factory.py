"""
factory.py — создание API-клиента по записи connections[].
"""
from constants import TOKEN_STUB


def create_api(conn: dict):
    """Возвращает клиент брокера (TBankAPI | BCSAPI)."""
    broker = conn.get("broker", "tbank")
    name   = conn.get("name") or broker
    token  = (conn.get("token") or "").strip()

    if broker == "tbank":
        from api.client import TBankAPI
        return TBankAPI(
            token,
            use_sandbox=conn.get("use_sandbox", False),
            label=name,
        )
    if broker == "bcs":
        from api.bcs_client import BCSAPI
        return BCSAPI(token, label=name)

    raise ValueError(f"Неподдерживаемый брокер: {broker}")


def verify_connection(broker: str, token: str, *, use_sandbox: bool = False) -> int:
    """
    Проверяет токен. Возвращает число счетов (для БКС всегда 1).
    Raises при ошибке.
    """
    token = (token or "").strip().strip('"').strip("'")
    if not token or token == TOKEN_STUB or len(token) < 10:
        raise ValueError("Токен слишком короткий или не задан")
    if broker not in ("tbank", "bcs"):
        raise ValueError(f"Неподдерживаемый брокер: {broker}")

    conn = {
        "broker": broker, "token": token,
        "name": "test", "use_sandbox": use_sandbox,
    }
    api = create_api(conn)
    if broker == "bcs":
        from api.bcs_client import BCSAPIError
        api._ensure_token()
        try:
            api.get_portfolio("bcs-main")
        except BCSAPIError as e:
            msg = str(e)
            if "SSLError" in msg or "SSL" in msg or "Connection" in msg:
                raise BCSAPIError(
                    "Токен принят, но сервер БКС временно недоступен (SSL/сеть). "
                    "Попробуйте через минуту или проверьте VPN/антивирус."
                ) from e
            raise
        return 1

    accounts = api.get_accounts()
    if not accounts:
        raise ValueError("Счета не найдены")
    return len(accounts)
