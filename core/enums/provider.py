from __future__ import annotations

from enum import StrEnum


class ProviderState(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class ProviderCapability(StrEnum):
    REALTIME_QUOTES = "realtime_quotes"
    HISTORICAL_OHLCV = "historical_ohlcv"
    ORDER_BOOK = "order_book"
    TRADES = "trades"
    NEWS = "news"
    FUNDAMENTAL = "fundamental"
    MACRO = "macro"
    REFERENCE = "reference"
    MANUAL_INPUT = "manual_input"


class AuthType(StrEnum):
    NONE = "none"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    CERTIFICATE = "certificate"
