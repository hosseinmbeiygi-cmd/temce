from __future__ import annotations

from typing import Any

from iran_market_data.app.collectors.base import BaseCollector


class FipiranCollector(BaseCollector):
    """Collector for Fipiran (مرکز پردازش اطلاعات مالی ایران).

    Fipiran provides a modern REST API covering both TSETMC data and fund data.

    Base API: https://www.fipiran.com/services/

    Instrument Endpoints:
      - instrument/instrumentcompare     - search/list all instruments
      - instrument/getinstrument?insCode=X - detailed instrument info
      - instrument/instrumenthistory?insCode=X&pageSize=N&pageIndex=0
      - instrument/instrumentperiodicstatistics?insCode=X&date=Y
      - instrument/getefficiency?insCode=X&date=Y
      - instrument/getindustry            - list industry groups
      - instrument/getindustrysub         - list sub-industries

    Fund Endpoints:
      - fund/fundcompare                  - list all funds
      - fund/getfund?regno=X              - specific fund details
      - fund/fundtype                     - fund type categories
      - fund/averagereturns               - average returns
      - fund/treemap                      - fund treemap data
      - fund/dependencygraph              - fund dependency graph

    Chart Endpoints:
      - chart/portfoliochart?regno=X            - asset allocation over time
      - chart/getfundchart?regno=X&showAll=true - NAV per unit history
      - chart/getfundnetassetchart?regno=X      - total NAV history
      - chart/alphabetachart?regno=X             - alpha/beta history

    Codal (via Fipiran):
      - codal/publisher?insCode=X          - publisher/company info
      - codal/statements?insCode=X&pageSize=N - financial statements

    Index:
      - index/indexcompare                 - index data comparison
    """

    source_name = "fipiran"
    BASE_URL = "https://www.fipiran.com"
    API_URL = "https://www.fipiran.com/services/"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.5,fa;q=0.3",
                "Referer": self.BASE_URL,
            }
        )

    def _api(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call Fipiran API and return parsed JSON."""
        url = self.API_URL + path.lstrip("/")
        response = self.http.get(url, params=params)
        return response.json()

    # ---- Instruments ----

    def collect_instrument_compare(
        self,
        symbol: str | None = None,
        market_type: str | None = None,
        symbol_type: str | None = None,
        industry: str | None = None,
        limit: int = 100,
        sort: str = "asc",
        column: str = "smallSymbolName",
    ) -> dict[str, Any]:
        """Search/list instruments with optional filters.

        Args:
            symbol: Persian symbol name (e.g. 'فملی')
            market_type: Market type code (1=TSE, 2=IFB, 6=Energy, 7=Commodity)
            symbol_type: Symbol type code (300=ordinary, 305=ETF, etc.)
            industry: Industry group code
            limit: Max results (default 100)
        """
        params: dict[str, Any] = {
            "pageIndex": 0,
            "pageSize": limit,
            "sort": sort,
            "column": column,
        }
        if symbol:
            params["symbol"] = symbol
        if market_type:
            params["markettype"] = market_type
        if symbol_type:
            params["symboltype"] = symbol_type
        if industry:
            params["industry"] = industry

        data = self._api("instrument/instrumentcompare", params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="instrument_compare",
            content=str(data),
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": data}

    def collect_instrument_info(self, ins_code: str) -> dict[str, Any]:
        """Get detailed info for a specific instrument including prices, orderbook, client types."""
        data = self._api("instrument/getinstrument", {"insCode": ins_code})
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"instrument_{ins_code}",
            content=str(data),
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": data}

    def collect_instrument_history(self, ins_code: str, limit: int = 100) -> dict[str, Any]:
        """Get daily OHLCV history for an instrument."""
        data = self._api(
            "instrument/instrumenthistory",
            {
                "insCode": ins_code,
                "pageSize": limit,
                "pageIndex": 0,
            },
        )
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"history_{ins_code}",
            content=str(data),
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": data}

    def collect_statistics(self, ins_code: str, date: str) -> dict[str, Any]:
        """Get periodic statistics (weekly, monthly, quarterly, annual)."""
        data = self._api(
            "instrument/instrumentperiodicstatistics",
            {
                "insCode": ins_code,
                "date": date,
            },
        )
        return {"data": data}

    def collect_efficiency(self, ins_code: str, date: str) -> dict[str, Any]:
        """Get efficiency/return data for an instrument."""
        data = self._api(
            "instrument/getefficiency",
            {
                "insCode": ins_code,
                "date": date,
            },
        )
        return {"data": data}

    def collect_industries(self) -> dict[str, Any]:
        """Get list of all industry groups."""
        data = self._api("instrument/getindustry")
        return {"data": data}

    def collect_sub_industries(self) -> dict[str, Any]:
        """Get list of all sub-industries."""
        data = self._api("instrument/getindustrysub")
        return {"data": data}

    # ---- Funds ----

    def collect_fund_compare(self) -> dict[str, Any]:
        """Get list of all funds with their latest NAV and performance data."""
        data = self._api("fund/fundcompare")
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="fund_compare",
            content=str(data),
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": data}

    def collect_fund_info(self, reg_no: str) -> dict[str, Any]:
        """Get detailed info for a specific fund.

        Args:
            reg_no: Fund registration number
        """
        data = self._api(f"fund/getfund?regno={reg_no}")
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"fund_{reg_no}",
            content=str(data),
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": data}

    def collect_fund_types(self) -> dict[str, Any]:
        """Get list of fund types/categories."""
        data = self._api("fund/fundtype")
        return {"data": data}

    def collect_fund_average_returns(self) -> dict[str, Any]:
        """Get average returns across all fund types."""
        data = self._api("fund/averagereturns")
        return {"data": data}

    def collect_fund_treemap(self) -> dict[str, Any]:
        """Get fund treemap data."""
        data = self._api("fund/treemap")
        return {"data": data}

    # ---- Charts ----

    def collect_portfolio_chart(self, reg_no: str) -> dict[str, Any]:
        """Get asset allocation history for a fund."""
        data = self._api(f"chart/portfoliochart?regno={reg_no}")
        return {"data": data}

    def collect_fund_navps_chart(self, reg_no: str, all_data: bool = True) -> dict[str, Any]:
        """Get NAV per unit history for a fund."""
        data = self._api(f"chart/getfundchart?regno={reg_no}&showAll={str(all_data).lower()}")
        return {"data": data}

    def collect_fund_nav_chart(self, reg_no: str, all_data: bool = True) -> dict[str, Any]:
        """Get total net asset value history for a fund."""
        data = self._api(f"chart/getfundnetassetchart?regno={reg_no}&showAll={str(all_data).lower()}")
        return {"data": data}

    def collect_alpha_beta_chart(self, reg_no: str, all_data: bool = True) -> dict[str, Any]:
        """Get alpha/beta history for a fund."""
        data = self._api(f"chart/alphabetachart?regno={reg_no}&showAll={str(all_data).lower()}")
        return {"data": data}

    # ---- Codal via Fipiran ----

    def collect_publisher_info(self, ins_code: str) -> dict[str, Any]:
        """Get publisher/company info from Codal via Fipiran."""
        data = self._api("codal/publisher", {"insCode": ins_code})
        return {"data": data}

    def collect_codal_statements(self, ins_code: str, limit: int = 50) -> dict[str, Any]:
        """Get financial statements for an instrument from Codal via Fipiran.

        Returns list of statements with titles, dates, and PDF/Excel URLs.
        """
        data = self._api(
            "codal/statements",
            {
                "insCode": ins_code,
                "pageSize": limit,
                "pageIndex": 0,
            },
        )
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"statements_{ins_code}",
            content=str(data),
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": data}

    # ---- Index ----

    def collect_index_compare(self) -> dict[str, Any]:
        """Get index comparison data (all indices performance)."""
        data = self._api("index/indexcompare")
        return {"data": data}

    # ---- Default Collection ----

    def collect(self) -> dict[str, Any]:
        """Run default collection: funds + instruments + index."""
        funds = self.collect_fund_compare()
        idx = self.collect_index_compare()
        industries = self.collect_industries()
        return {
            "funds": funds,
            "index": idx,
            "industries": industries,
            "status": "ok",
        }
