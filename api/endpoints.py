"""
api_endpoints.py — все эндпоинты T-Bank Invest REST API в одном месте.

Базовые URL:
  Prod:    https://invest-public-api.tinkoff.ru/rest
  Sandbox: https://sandbox-invest-public-api.tinkoff.ru/rest

Документация: https://developer.tbank.ru/invest/api
"""

API_BASE_PROD    = "https://invest-public-api.tinkoff.ru/rest"
API_BASE_SANDBOX = "https://sandbox-invest-public-api.tinkoff.ru/rest"

# Префикс всех методов
_P = "tinkoff.public.invest.api.contract.v1"

# ── UsersService ─────────────────────────────────────────────────────────────
GET_ACCOUNTS       = f"{_P}.UsersService/GetAccounts"

# ── OperationsService ────────────────────────────────────────────────────────
GET_PORTFOLIO      = f"{_P}.OperationsService/GetPortfolio"

# ── InstrumentsService ───────────────────────────────────────────────────────
BOND_BY            = f"{_P}.InstrumentsService/BondBy"
SHARE_BY           = f"{_P}.InstrumentsService/ShareBy"
GET_INSTRUMENT_BY  = f"{_P}.InstrumentsService/GetInstrumentBy"
GET_BOND_COUPONS   = f"{_P}.InstrumentsService/GetBondCoupons"

# ── Типы ID инструментов ────────────────────────────────────────────────────
ID_TYPE_FIGI       = "INSTRUMENT_ID_TYPE_FIGI"

# ── CDN логотипов ────────────────────────────────────────────────────────────
LOGO_CDN           = "https://invest-brands.cdn-tinkoff.ru/{logo_id}x160.png"

# ── Ссылки на инструменты (для открытия в браузере) ──────────────────────────
TBANK_BONDS_URL    = "https://www.tbank.ru/invest/bonds/{ticker}/"
TBANK_STOCKS_URL   = "https://www.tbank.ru/invest/stocks/{ticker}/"
TBANK_ETFS_URL     = "https://www.tbank.ru/invest/etfs/{ticker}/"
TBANK_CURRENCY_URL = "https://www.tbank.ru/invest/currencies/{ticker}/"
TBANK_PORTFOLIO_URL= "https://www.tbank.ru/invest/portfolio/"
