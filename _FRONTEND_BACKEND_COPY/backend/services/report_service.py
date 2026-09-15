from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from reports.builders.backtest_report_builder import BacktestReportBuilder
from reports.builders.market_report_builder import MarketReportBuilder
from reports.builders.portfolio_report_builder import PortfolioReportBuilder
from reports.builders.symbol_report_builder import SymbolReportBuilder
from reports.exporters.csv_exporter import CsvExporter
from reports.exporters.html_exporter import HtmlExporter
from reports.exporters.json_exporter import JsonExporter

logger = get_logger(__name__)


def _build_market_builder(session: AsyncSession | None = None) -> MarketReportBuilder:
    from services.market_service import MarketService

    return MarketReportBuilder(market_service=MarketService(session=session))


def _build_symbol_builder(session: AsyncSession | None = None) -> SymbolReportBuilder:
    from services.analytics_service import AnalyticsService
    from services.quote_service import QuoteService
    from services.symbol_service import SymbolService

    return SymbolReportBuilder(
        symbol_service=SymbolService(session=session),
        quote_service=QuoteService(session=session),
        analytics_service=AnalyticsService(session=session),
    )


class ReportService:
    def __init__(
        self,
        market_builder: MarketReportBuilder | None = None,
        symbol_builder: SymbolReportBuilder | None = None,
        portfolio_builder: PortfolioReportBuilder | None = None,
        backtest_builder: BacktestReportBuilder | None = None,
        csv_exporter: CsvExporter | None = None,
        json_exporter: JsonExporter | None = None,
        html_exporter: HtmlExporter | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._session = session
        self._market_builder = market_builder or _build_market_builder(session)
        self._symbol_builder = symbol_builder or _build_symbol_builder(session)
        self._portfolio_builder = portfolio_builder or PortfolioReportBuilder()
        self._backtest_builder = backtest_builder or BacktestReportBuilder()
        self._csv_exporter = csv_exporter or CsvExporter()
        self._json_exporter = json_exporter or JsonExporter()
        self._html_exporter = html_exporter or HtmlExporter()

    async def generate_market_report(self, date: str | None = None) -> Result[dict[str, Any]]:
        logger.info("Generating market report for date=%s", date)
        result = await self._market_builder.build(date=date)
        if not result.success:
            return Result.fail(f"Failed to generate market report: {result.error}")
        data = result.value
        report_id = new_id("rpt")
        data["report_id"] = report_id
        logger.info("Market report generated: %s", report_id)
        return Result.ok(data)

    async def generate_symbol_report(
        self, symbol_id: str, date_range: dict[str, str] | None = None
    ) -> Result[dict[str, Any]]:
        logger.info("Generating symbol report for symbol=%s", symbol_id)
        timeframe = "1d"
        if date_range and "timeframe" in date_range:
            timeframe = date_range["timeframe"]
        result = await self._symbol_builder.build(symbol=symbol_id, timeframe=timeframe)
        if not result.success:
            return Result.fail(f"Failed to generate symbol report: {result.error}")
        data = result.value
        report_id = new_id("rpt")
        data["report_id"] = report_id
        if date_range:
            data["date_range"] = date_range
        logger.info("Symbol report generated: %s", report_id)
        return Result.ok(data)

    async def generate_portfolio_report(self, portfolio_id: str) -> Result[dict[str, Any]]:
        logger.info("Generating portfolio report for portfolio=%s", portfolio_id)
        try:
            from repositories.portfolio_repository import PortfolioRepository

            repo = PortfolioRepository()
            portfolio_result = await repo.get(portfolio_id)
            if portfolio_result is None:
                return Result.fail(f"Portfolio not found: {portfolio_id}")
            result = await self._portfolio_builder.build(portfolio_result)
        except ImportError:
            result = await self._portfolio_builder.build(portfolio_id)
        except Exception as e:
            return Result.fail(f"Failed to generate portfolio report: {e}")
        if not result.success:
            return Result.fail(f"Failed to generate portfolio report: {result.error}")
        data = result.value
        report_id = new_id("rpt")
        data["report_id"] = report_id
        logger.info("Portfolio report generated: %s", report_id)
        return Result.ok(data)

    async def generate_backtest_report(self, backtest_id: str) -> Result[dict[str, Any]]:
        logger.info("Generating backtest report for backtest=%s", backtest_id)
        try:
            result = await self._backtest_builder.build({"backtest_id": backtest_id})
        except Exception:
            result = await self._backtest_builder.build({"backtest_id": backtest_id})
        if not result.success:
            return Result.fail(f"Failed to generate backtest report: {result.error}")
        data = result.value
        report_id = new_id("rpt")
        data["report_id"] = report_id
        logger.info("Backtest report generated: %s", report_id)
        return Result.ok(data)

    async def export_csv(self, data: list[dict[str, Any]], filename: str | None = None) -> Result[str]:
        if not data:
            return Result.fail("No data to export")
        output_path = filename or f"{new_id('csv')}.csv"
        result = await self._csv_exporter.export(data, output_path=output_path)
        if not result.success:
            return Result.fail(f"CSV export failed: {result.error}")
        logger.info("CSV exported to %s", result.value)
        return Result.ok(result.value)

    async def export_json(self, data: Any, filename: str | None = None) -> Result[str]:
        output_path = filename or f"{new_id('json')}.json"
        result = await self._json_exporter.export(data, output_path=output_path)
        if not result.success:
            return Result.fail(f"JSON export failed: {result.error}")
        logger.info("JSON exported to %s", result.value)
        return Result.ok(result.value)

    async def export_html(self, data: dict[str, Any], template_name: str | None = None) -> Result[str]:
        output_path = data.get("output_path") or f"{new_id('html')}.html"
        result = await self._html_exporter.export(data, output_path=output_path)
        if not result.success:
            return Result.fail(f"HTML export failed: {result.error}")
        logger.info("HTML exported to %s", result.value)
        return Result.ok(result.value)
