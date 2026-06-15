from __future__ import annotations

from typing import Any

from iran_market_data.app.collectors.base import BaseCollector


class TsetmcCollector(BaseCollector):
    """Collector for TSETMC (Tehran Stock Exchange).

    Endpoints (old system - old.tsetmc.com):
      - MarketWatchPlus: /tsev2/data/MarketWatchPlus.aspx?h={heven}&r={refid}
      - ClientTypeAll:   /tsev2/data/ClientTypeAll.aspx
      - InstInfo:        /tsev2/data/instinfodata.aspx?i={id}&c=27
      - TradeHistory:    /tsev2/data/InstTradeHistory.aspx?i={id}&Top=999999&A=0
      - InstValue:       /tsev2/data/InstValue.aspx?t=a
      - ClosingPriceAll: /tsev2/data/ClosingPriceAll.aspx

    Endpoints (new CDN system - cdn.tsetmc.com/api):
      - ClosingPriceDaily:   /api/ClosingPrice/GetClosingPriceDaily/{id}/{date}
      - ClosingPriceHistory: /api/ClosingPrice/GetClosingPriceHistory/{id}/{date}
      - BestLimits:          /api/BestLimits/{id}/{date}
      - TradeHistory:        /api/Trade/GetTradeHistory/{id}/{date}/{summarize}
      - ClientTypeHistory:   /api/ClientType/GetClientTypeHistory/{id}
      - MarketMap:           /api/ClosingPrice/GetMarketMap?market=0&size=1920&sector=0
    """

    source_name = "tsetmc"
    BASE_OLD = "http://old.tsetmc.com"
    BASE_CDN = "https://cdn.tsetmc.com"
    BASE_MEMBERS = "https://members.tsetmc.com"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    # ---- Old System Endpoints ----

    def collect_market_watch(self, heven: int = 0, refid: int = 0) -> dict[str, Any]:
        """Collect real-time market watch data from old TSETMC.

        Returns raw text response containing pipe-delimited price & orderbook data.
        """
        url = f"{self.BASE_OLD}/tsev2/data/MarketWatchPlus.aspx"
        params = {"h": heven, "r": refid}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="market_watch",
            content=response.text,
            file_format="txt",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_client_type_all(self) -> dict[str, Any]:
        """Collect client type data (real/legal buy/sell) for all symbols."""
        url = f"{self.BASE_OLD}/tsev2/data/ClientTypeAll.aspx"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="client_type_all",
            content=response.text,
            file_format="txt",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_instrument_info(self, ins_code: str) -> dict[str, Any]:
        """Collect detailed instrument info including price, orderbook, client types.

        Args:
            ins_code: TSETMC instrument code (e.g. '43362635835198978')
        """
        url = f"{self.BASE_OLD}/tsev2/data/instinfodata.aspx"
        params = {"i": ins_code, "c": 27}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"inst_info_{ins_code}",
            content=response.text,
            file_format="txt",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_trade_history(self, ins_code: str) -> dict[str, Any]:
        """Collect daily trade history (OHLCV) for an instrument.

        Args:
            ins_code: TSETMC instrument code
        """
        url = f"{self.BASE_OLD}/tsev2/data/InstTradeHistory.aspx"
        params = {"i": ins_code, "Top": 999999, "A": 0}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"trade_history_{ins_code}",
            content=response.text,
            file_format="txt",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_closing_prices_all(self) -> dict[str, Any]:
        """Collect closing prices for ALL instruments (daily snapshot)."""
        url = f"{self.BASE_MEMBERS}/tsev2/data/ClosingPriceAll.aspx"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="closing_prices_all",
            content=response.text,
            file_format="txt",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_instrument_stats(self) -> dict[str, Any]:
        """Collect statistical data for all instruments."""
        url = f"{self.BASE_OLD}/tsev2/data/InstValue.aspx"
        params = {"t": "a"}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="inst_stats_all",
            content=response.text,
            file_format="txt",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_codal_notifications(self, ins_code: str) -> dict[str, Any]:
        """Fetch latest codal notifications for an instrument from TSETMC."""
        url = f"{self.BASE_OLD}/tsev2/data/CodalTopNew.aspx"
        params = {"i": ins_code}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"codal_notifs_{ins_code}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_loader_page(self, ins_code: str, partree: str = "15131M") -> dict[str, Any]:
        """Fetch a loader page (e.g. Partree=15131M for instrument details).

        Common Partree values:
          15131M - instrument details (ISIN, names, sector)
          15131W - supervisor messages
          15131L - state changes
          15131T - shareholders
        """
        url = f"{self.BASE_OLD}/Loader.aspx"
        params = {"i": ins_code, "Partree": partree}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"loader_{partree}_{ins_code}",
            content=response.text,
            file_format="html",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    # ---- New CDN API Endpoints ----

    def collect_closing_price_daily(self, ins_code: str, date: str) -> dict[str, Any]:
        """Collect daily closing price from new CDN API.

        Args:
            ins_code: TSETMC instrument code
            date: Gregorian date in YYYYMMDD format
        """
        url = f"{self.BASE_CDN}/api/ClosingPrice/GetClosingPriceDaily/{ins_code}/{date}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"cp_daily_{ins_code}_{date}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_closing_price_history(self, ins_code: str, date: str) -> dict[str, Any]:
        """Collect intraday closing price history from new CDN API."""
        url = f"{self.BASE_CDN}/api/ClosingPrice/GetClosingPriceHistory/{ins_code}/{date}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"cp_history_{ins_code}_{date}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_best_limits(self, ins_code: str, date: str) -> dict[str, Any]:
        """Collect order book (best limits) data from CDN API."""
        url = f"{self.BASE_CDN}/api/BestLimits/{ins_code}/{date}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"best_limits_{ins_code}_{date}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_trade_detail(self, ins_code: str, date: str, summarize: bool = True) -> dict[str, Any]:
        """Collect detailed trade history (tick-by-tick or summarized)."""
        url = f"{self.BASE_CDN}/api/Trade/GetTradeHistory/{ins_code}/{date}/{str(summarize).lower()}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"trades_{ins_code}_{date}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_client_type_history(self, ins_code: str) -> dict[str, Any]:
        """Collect client type history from CDN API."""
        url = f"{self.BASE_CDN}/api/ClientType/GetClientTypeHistory/{ins_code}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"client_type_{ins_code}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_market_map(self, map_type: int = 0, heven: int = 0) -> dict[str, Any]:
        """Collect market map data."""
        url = f"{self.BASE_CDN}/api/ClosingPrice/GetMarketMap"
        params = {"market": 0, "size": 1920, "sector": 0, "typeSelected": map_type, "hEven": heven}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="market_map",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_shareholders(self, ins_code: str, date: str) -> dict[str, Any]:
        """Collect shareholder data for an instrument on a given date."""
        url = f"{self.BASE_CDN}/api/Shareholder/{ins_code}/{date}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"shareholders_{ins_code}_{date}",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    # ---- Default Collection ----

    def collect(self) -> dict[str, Any]:
        """Run default collection: market watch + client type."""
        mw = self.collect_market_watch()
        ct = self.collect_client_type_all()
        return {
            "market_watch": mw,
            "client_type": ct,
            "status": "ok",
        }
