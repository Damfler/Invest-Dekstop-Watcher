"""
bcs_endpoints.py — URL и пути BCS Trade API.
Документация: https://trade-api.bcs.ru/
"""

AUTH_URL = (
    "https://be.broker.ru/trade-api-keycloak/realms/tradeapi/protocol/openid-connect/token"
)
PORTFOLIO_BASE = "https://be.broker.ru/trade-api-bff-portfolio/api/v1"
LIMITS_BASE    = "https://be.broker.ru/trade-api-bff-limit/api/v1"
INFO_BASE      = "https://be.broker.ru/trade-api-information-service/api/v1"
MARKET_BASE    = "https://be.broker.ru/trade-api-market-data-connector/api/v1"

CLIENT_ID_READ  = "trade-api-read"
CLIENT_ID_WRITE = "trade-api-write"

# classCode → instrumentType для Stack
BOND_CLASS_CODES = frozenset({"TQOB", "TQCB", "TQIR", "TQRD", "TQOY", "TQOD", "AUBB"})
ETF_CLASS_CODES  = frozenset({"TQTF", "TQIF", "TQTE"})
CURRENCY_CLASS   = frozenset({"CETS", "CNGD", "CROSSRATE"})
