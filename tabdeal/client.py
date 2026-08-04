"""
Tabdeal API client.

Handles authentication (HMAC-SHA256), HTTP requests, and pagination
for both Spot and Futures (FAPI) endpoints.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api1.tabdeal.org"
SPOT_PREFIX = "/api/v1"
SPOT_READ_PREFIX = "/r/api/v1"
FAPI_PREFIX = "/fapi/v1"
FAPI_READ_PREFIX = "/r/fapi/v1"


class TabdealClient:
    """
    Async client for the Tabdeal exchange API.

    Usage::

        client = TabdealClient(api_key="...", api_secret="...")
        account = await client.get_account()
        orders = await client.get_open_orders(symbol="BTCIRT")
    """

    def __init__(self, api_key: str = "", api_secret: str = "", timeout: float = 15.0):
        self.api_key = api_key
        self.api_secret = api_secret
        self._http = httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)

    async def close(self):
        await self._http.aclose()

    # ── Auth helpers ──────────────────────────────────────────────

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add timestamp + HMAC-SHA256 signature to params."""
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key} if self.api_key else {}

    # ── Generic request ───────────────────────────────────────────

    async def _get(self, path: str, params: dict[str, Any] | None = None, auth: bool = True) -> Any:
        p = dict(params or {})
        if auth and self.api_secret:
            p = self._sign(p)
        resp = await self._http.get(path, params=p, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: dict[str, Any] | None = None, auth: bool = True) -> Any:
        p = dict(data or {})
        if auth and self.api_secret:
            p = self._sign(p)
        resp = await self._http.post(path, data=p, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str, params: dict[str, Any] | None = None, auth: bool = True) -> Any:
        p = dict(params or {})
        if auth and self.secret:
            p = self._sign(p)
        resp = await self._http.delete(path, params=p, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ══════════════════════════════════════════════════════════════
    #  SPOT — Market Data (NONE)
    # ══════════════════════════════════════════════════════════════

    async def ping(self) -> dict:
        return await self._get(f"{SPOT_READ_PREFIX}/ping", auth=False)

    async def server_time(self) -> dict:
        return await self._get(f"{SPOT_READ_PREFIX}/time", auth=False)

    async def exchange_info(self, symbol: str | None = None, symbols: list[str] | None = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        elif symbols:
            params["symbols"] = ",".join(symbols)
        return await self._get(f"{SPOT_READ_PREFIX}/exchangeInfo", params, auth=False)

    async def depth(self, symbol: str, limit: int = 100) -> dict:
        return await self._get(f"{SPOT_READ_PREFIX}/depth", {"symbol": symbol, "limit": limit}, auth=False)

    async def trades(self, symbol: str, limit: int = 50) -> list:
        return await self._get(f"{SPOT_READ_PREFIX}/trades", {"symbol": symbol, "limit": limit}, auth=False)

    # ══════════════════════════════════════════════════════════════
    #  SPOT — Trading (TRADE)
    # ══════════════════════════════════════════════════════════════

    async def new_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None = None,
        stop_price: str | None = None,
        new_client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"symbol": symbol, "side": side, "type": order_type, "quantity": quantity}
        if price:
            params["price"] = price
        if stop_price:
            params["stopPrice"] = stop_price
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        return await self._post(f"{SPOT_PREFIX}/order", params)

    async def get_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._get(f"{SPOT_READ_PREFIX}/order", params)

    async def get_open_orders(self, symbol: str | None = None) -> list:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self._get(f"{SPOT_READ_PREFIX}/openOrders", params)

    async def get_paginated_open_orders(self, symbol: str | None = None, page: int = 1, page_size: int = 100) -> dict:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if symbol:
            params["symbol"] = symbol
        return await self._get(f"{SPOT_READ_PREFIX}/paginatedOpenOrders", params)

    async def cancel_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._delete(f"{SPOT_PREFIX}/order", params)

    async def cancel_open_orders(self, symbol: str) -> list:
        return await self._delete(f"{SPOT_PREFIX}/openOrders", {"symbol": symbol})

    async def get_all_orders(
        self, symbol: str | None = None, start_time: int | None = None, end_time: int | None = None, limit: int = 50
    ) -> list:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._get(f"{SPOT_READ_PREFIX}/allOrders", params)

    async def get_non_expired_all_orders(
        self, start_time: int | None = None, end_time: int | None = None, limit: int = 50
    ) -> list:
        params: dict[str, Any] = {"limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._delete(f"{SPOT_PREFIX}/nonExpiredAllOrders", params)

    # ── OCO ──

    async def new_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        stop_price: str,
        stop_limit_price: str,
        list_client_order_id: str | None = None,
        limit_client_order_id: str | None = None,
        stop_client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "stopPrice": stop_price,
            "stopLimitPrice": stop_limit_price,
        }
        if list_client_order_id:
            params["listClientOrderId"] = list_client_order_id
        if limit_client_order_id:
            params["limitClientOrderId"] = limit_client_order_id
        if stop_client_order_id:
            params["stopClientOrderId"] = stop_client_order_id
        return await self._post(f"{SPOT_PREFIX}/order/oco", params)

    async def get_oco_order(self, order_list_id: int | None = None, client_order_id: str | None = None) -> dict:
        params: dict[str, Any] = {}
        if order_list_id:
            params["orderListId"] = order_list_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._get(f"{SPOT_READ_PREFIX}/orderList", params)

    async def get_oco_open_orders(self) -> list:
        return await self._get(f"{SPOT_READ_PREFIX}/openOrderList")

    async def cancel_oco_order(self, symbol: str, order_list_id: int | None = None, list_client_order_id: str | None = None) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_list_id:
            params["orderListId"] = order_list_id
        if list_client_order_id:
            params["listClientOrderId"] = list_client_order_id
        return await self._delete(f"{SPOT_PREFIX}/orderList", params)

    async def get_oco_orders(self, start_time: int | None = None, end_time: int | None = None, limit: int = 50) -> list:
        params: dict[str, Any] = {"limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._get(f"{SPOT_READ_PREFIX}/allOrderList", params)

    # ── Trades & Account ──

    async def my_trades(
        self, symbol: str, start_time: int | None = None, end_time: int | None = None, limit: int = 50, order_id: int | None = None
    ) -> list:
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        if order_id:
            params["orderId"] = order_id
        return await self._get(f"{SPOT_READ_PREFIX}/myTrades", params)

    async def account(self) -> dict:
        return await self._get(f"{SPOT_READ_PREFIX}/account")

    async def funding_wallet(self, asset: str | None = None) -> dict:
        params: dict[str, Any] = {}
        if asset:
            params["asset"] = asset
        return await self._get(f"{SPOT_READ_PREFIX}/asset/get-funding-asset", params)

    # ── Listen Key ──

    async def new_listen_key(self) -> dict:
        return await self._post(f"{SPOT_PREFIX}/userDataStream", auth=False)

    async def renew_listen_key(self, listen_key: str) -> dict:
        return await self._http.put(f"{SPOT_PREFIX}/userDataStream", data={"listenKey": listen_key}, headers=self._headers())

    async def close_listen_key(self, listen_key: str) -> dict:
        return await self._http.delete(f"{SPOT_PREFIX}/userDataStream", params={"listenKey": listen_key}, headers=self._headers())

    # ══════════════════════════════════════════════════════════════
    #  ISOLATED MARGIN
    # ══════════════════════════════════════════════════════════════

    async def margin_transfer(self, asset: str, amount: str, trans_from: str, trans_to: str, symbol: str) -> dict:
        return await self._post(f"{SPOT_READ_PREFIX}/margin/isolated/transfer", {
            "asset": asset, "amount": amount, "transFrom": trans_from, "transTo": trans_to, "symbol": symbol,
        })

    async def get_margin_open_orders(self, symbol: str | None = None) -> list:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self._get(f"{SPOT_READ_PREFIX}/margin/openOrders", params)

    async def create_margin_order(
        self, symbol: str, side: str, order_type: str, quantity: str,
        borrow_quantity: str, price: str | None = None, stop_price: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {
            "symbol": symbol, "side": side, "type": order_type,
            "quantity": quantity, "borrow_quantity": borrow_quantity,
        }
        if price:
            params["price"] = price
        if stop_price:
            params["stopPrice"] = stop_price
        return await self._post(f"{SPOT_PREFIX}/margin/order", params)

    async def get_margin_order(self, symbol: str, order_id: int | None = None) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        return await self._get(f"{SPOT_READ_PREFIX}/margin/order", params)

    async def cancel_margin_order(self, symbol: str, order_id: int | None = None) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        return await self._delete(f"{SPOT_PREFIX}/margin/order", params)

    async def get_margin_account(self, symbols: list[str] | None = None) -> dict:
        params: dict[str, Any] = {}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return await self._get(f"{SPOT_PREFIX}/margin/isolated/account", params)

    # ══════════════════════════════════════════════════════════════
    #  FAPI (Professional Futures)
    # ══════════════════════════════════════════════════════════════

    async def fapi_ping(self) -> dict:
        return await self._get(f"{FAPI_READ_PREFIX}/ping", auth=False)

    async def fapi_time(self) -> dict:
        return await self._get(f"{FAPI_READ_PREFIX}/time", auth=False)

    async def fapi_exchange_info(self, symbol: str | None = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self._get(f"{FAPI_READ_PREFIX}/exchangeInfo", params, auth=False)

    async def fapi_depth(self, symbol: str, limit: int = 100) -> dict:
        return await self._get(f"{FAPI_READ_PREFIX}/depth", {"symbol": symbol, "limit": limit}, auth=False)

    async def fapi_new_order(
        self, symbol: str, side: str, order_type: str, quantity: str,
        price: str | None = None, time_in_force: str | None = None,
        reduce_only: bool = False, new_client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"symbol": symbol, "side": side, "type": order_type, "quantity": quantity}
        if price:
            params["price"] = price
        if time_in_force:
            params["timeInForce"] = time_in_force
        if reduce_only:
            params["reduceOnly"] = "true"
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        return await self._post(f"{FAPI_PREFIX}/order", params)

    async def fapi_get_order(self, symbol: str, order_id: int) -> dict:
        return await self._get(f"{FAPI_READ_PREFIX}/order", {"symbol": symbol, "orderId": order_id})

    async def fapi_cancel_order(self, symbol: str, order_id: int) -> dict:
        return await self._delete(f"{FAPI_PREFIX}/order", {"symbol": symbol, "orderId": order_id})

    async def fapi_open_orders(self, symbol: str | None = None, limit: int = 50) -> list:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        return await self._get(f"{FAPI_READ_PREFIX}/openOrders", params)

    async def fapi_all_orders(
        self, symbol: str, start_time: int | None = None, end_time: int | None = None, limit: int = 50
    ) -> list:
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._get(f"{FAPI_READ_PREFIX}/allOrders", params)

    async def fapi_position_risk(self, symbol: str | None = None) -> list:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self._get(f"{FAPI_READ_PREFIX}/positionRisk", params)

    async def fapi_get_leverage(self, symbol: str) -> dict:
        return await self._get(f"{FAPI_READ_PREFIX}/leverage", {"symbol": symbol})

    async def fapi_change_leverage(self, symbol: str, leverage: int) -> dict:
        return await self._post(f"{FAPI_PREFIX}/leverage", {"symbol": symbol, "leverage": leverage})

    async def fapi_account(self) -> dict:
        return await self._get(f"{FAPI_READ_PREFIX}/account")

    async def fapi_balance(self) -> list:
        return await self._get(f"{FAPI_READ_PREFIX}/balance")

    async def fapi_transfer(self, transfer_type: int, amount: str, asset: str) -> dict:
        return await self._post(f"{FAPI_PREFIX}/transfer", {"type": transfer_type, "amount": amount, "asset": asset})

    async def fapi_transfer_history(self, transfer_type: int | None = None, limit: int = 50) -> list:
        params: dict[str, Any] = {"limit": limit}
        if transfer_type:
            params["type"] = transfer_type
        return await self._get(f"{FAPI_READ_PREFIX}/transfer", params)

    async def fapi_user_trades(self, symbol: str, start_time: int | None = None, end_time: int | None = None, limit: int = 50) -> list:
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._get(f"{FAPI_READ_PREFIX}/userTrades", params)

    async def fapi_income(self, symbol: str | None = None, income_type: str | None = None, limit: int = 100) -> list:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if income_type:
            params["incomeType"] = income_type
        return await self._get(f"{FAPI_READ_PREFIX}/income", params)

    async def fapi_close_position(self, symbol: str) -> dict:
        return await self._delete(f"{FAPI_PREFIX}/position", {"symbol": symbol})

    async def fapi_position_sl_tp(
        self, position_id: int, symbol: str | None = None,
        sl_price: str | None = None, tp_price: str | None = None,
        working_type: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"positionId": position_id}
        if symbol:
            params["symbol"] = symbol
        if sl_price:
            params["slPrice"] = sl_price
        if tp_price:
            params["tpPrice"] = tp_price
        if working_type:
            params["workingType"] = working_type
        return await self._post(f"{FAPI_PREFIX}/positionSlTp", params)
