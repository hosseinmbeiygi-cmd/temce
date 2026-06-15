from __future__ import annotations

from typing import Any

from domain.analytics.indicator import Indicator
from domain.analytics.recommendation import Recommendation
from domain.analytics.signal import Signal
from domain.instruments.entities import Instrument
from domain.market_data.quote import Quote


class DocumentMapper:
    @staticmethod
    def instrument_to_document(instrument: Instrument) -> dict[str, Any]:
        return {
            "id": instrument.id,
            "symbol": getattr(instrument, "symbol", ""),
            "name": getattr(instrument, "name", ""),
            "isin": getattr(instrument, "isin", ""),
            "market": getattr(instrument, "market", ""),
            "asset_class": getattr(instrument, "asset_class", ""),
            "sector": getattr(instrument, "sector", ""),
            "status": getattr(instrument, "status", ""),
            "group_code": getattr(instrument, "group_code", ""),
            "type": "instrument",
        }

    @staticmethod
    def quote_to_document(quote: Quote) -> dict[str, Any]:
        return {
            "id": quote.id,
            "instrument_id": quote.instrument_id,
            "symbol": quote.symbol,
            "price_close": quote.price_close,
            "price_last": quote.price_last,
            "price_change_pct": quote.price_change_pct,
            "volume": quote.volume,
            "value": quote.value,
            "date": quote.date,
            "timeframe": quote.timeframe,
            "type": "quote",
        }

    @staticmethod
    def signal_to_document(signal: Signal) -> dict[str, Any]:
        return {
            "id": signal.id,
            "instrument_id": signal.instrument_id,
            "symbol": signal.symbol,
            "signal_type": signal.signal_type.value
            if hasattr(signal.signal_type, "value")
            else str(signal.signal_type),
            "score": signal.score,
            "confidence": signal.confidence,
            "source": signal.source,
            "strategy": signal.strategy,
            "date": signal.date,
            "timeframe": signal.timeframe,
            "description": signal.description,
            "type": "signal",
        }

    @staticmethod
    def recommendation_to_document(rec: Recommendation) -> dict[str, Any]:
        return {
            "id": rec.id,
            "instrument_id": rec.instrument_id,
            "symbol": rec.symbol,
            "action": rec.action.value if hasattr(rec.action, "value") else str(rec.action),
            "target_price": rec.target_price,
            "current_price": rec.current_price,
            "potential_return_pct": rec.potential_return_pct,
            "confidence": rec.confidence,
            "source": rec.source,
            "analyst": rec.analyst,
            "rationale": rec.rationale,
            "horizon": rec.horizon,
            "type": "recommendation",
        }

    @staticmethod
    def indicator_to_document(indicator: Indicator) -> dict[str, Any]:
        return {
            "id": indicator.id,
            "instrument_id": indicator.instrument_id,
            "symbol": indicator.symbol,
            "indicator_type": indicator.indicator_type,
            "value": indicator.value,
            "signal": indicator.signal,
            "date": indicator.date,
            "timeframe": indicator.timeframe,
            "type": "indicator",
        }

    @staticmethod
    def document_to_type(doc: dict[str, Any], doc_type: str) -> Any:
        mapping = {
            "instrument": DocumentMapper._doc_to_instrument,
            "quote": DocumentMapper._doc_to_quote,
            "signal": DocumentMapper._doc_to_signal,
            "recommendation": DocumentMapper._doc_to_recommendation,
        }
        converter = mapping.get(doc_type)
        if converter:
            return converter(doc)
        return doc

    @staticmethod
    def _doc_to_instrument(doc: dict[str, Any]) -> Instrument:
        return Instrument(id=doc.get("id", ""), name=doc.get("name", ""), symbol=doc.get("symbol", ""))

    @staticmethod
    def _doc_to_quote(doc: dict[str, Any]) -> Quote:
        return Quote(id=doc.get("id", ""), instrument_id=doc.get("instrument_id", ""), symbol=doc.get("symbol", ""))

    @staticmethod
    def _doc_to_signal(doc: dict[str, Any]) -> Signal:
        from domain.common.enum_types import SignalType

        st = SignalType.BULLISH
        return Signal(id=doc.get("id", ""), instrument_id=doc.get("instrument_id", ""), signal_type=st)

    @staticmethod
    def _doc_to_recommendation(doc: dict[str, Any]) -> Recommendation:
        from domain.common.enum_types import RecommendationAction

        return Recommendation(
            id=doc.get("id", ""), instrument_id=doc.get("instrument_id", ""), action=RecommendationAction.HOLD
        )
