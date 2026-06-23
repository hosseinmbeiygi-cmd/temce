from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from schemas.common.responses import ApiResponse

router = APIRouter()


class SentimentResponse(BaseModel):
    overall_sentiment: str
    sentiment_score: float
    indicators: dict[str, float]
    bullish_factors: list[str]
    bearish_factors: list[str]
    fear_greed_index: int
    date: str


class TrendResponse(BaseModel):
    sector: str
    trend: str
    confidence: int
    symbols: list[str]
    reasons: str


class RecommendationResponse(BaseModel):
    symbol: str
    action: str
    confidence: int
    target_price: int | None
    stop_loss: int | None
    current_price: int
    upside: float | None
    reason: str | None
    timeframe: str | None


class ElliotWaveResponse(BaseModel):
    symbol: str
    wave_count: int
    current_wave: int
    waves: list[dict[str, Any]]
    fibonacci_levels: dict[str, int]
    target_price: int
    stop_loss: int
    pattern: str
    analysis: str


class LiquidityResponse(BaseModel):
    date: str
    total_trade_value: int
    total_trade_volume: int
    total_inflow: int
    total_outflow: int
    net_flow: int
    institutional_flow: int
    retail_flow: int
    top_inflow_sectors: list[dict[str, Any]]
    top_outflow_sectors: list[dict[str, Any]]
    money_flow_index: float
    interpretation: str


class InterestRateResponse(BaseModel):
    date: str
    interest_rates: dict[str, float]
    sana_rate: float
    currency_rates: dict[str, dict[str, Any]]
    global_rates: dict[str, float]
    analysis: str


class AnalysisOverviewFrontend(BaseModel):
    sentiment: list[dict[str, Any]]
    trends: dict[str, Any]
    recommendations: list[dict[str, Any]]
    market_status: str
    analysis_date: str


@router.get("/overview")
async def analysis_overview_frontend() -> ApiResponse[AnalysisOverviewFrontend]:
    return ApiResponse[AnalysisOverviewFrontend](
        success=True,
        data=AnalysisOverviewFrontend(
            sentiment=[
                {"date": "1403-06-15", "score": 72, "label": "مثبت", "volume": 12500000000},
                {"date": "1403-06-14", "score": 65, "label": "مثبت", "volume": 11200000000},
                {"date": "1403-06-13", "score": 48, "label": "خنثی", "volume": 9800000000},
                {"date": "1403-06-12", "score": 35, "label": "منفی", "volume": 8500000000},
                {"date": "1403-06-11", "score": 42, "label": "خنثی", "volume": 10200000000},
                {"date": "1403-06-10", "score": 58, "label": "خنثی", "volume": 11500000000},
                {"date": "1403-06-09", "score": 61, "label": "مثبت", "volume": 10800000000},
            ],
            trends={
                "trend": "bullish",
                "strength": 68,
                "gainers": [
                    {"symbol": "فولاد", "change": 3.45},
                    {"symbol": "شپنا", "change": 2.18},
                    {"symbol": "وبملت", "change": 1.75},
                    {"symbol": "خودرو", "change": 1.32},
                ],
                "losers": [
                    {"symbol": "کگل", "change": -1.28},
                    {"symbol": "سیدکو", "change": -0.95},
                    {"symbol": "فملی", "change": -0.72},
                ],
            },
            recommendations=[
                {"symbol": "فولاد", "name": "فولاد مبارکه اصفهان", "signal": "buy", "targetPrice": 52000, "currentPrice": 42500, "upside": 22.35, "analyst": "تحلیل کارگزاری مفید"},
                {"symbol": "شپنا", "name": "پالایش نفت اصفهان", "signal": "buy", "targetPrice": 68000, "currentPrice": 53500, "upside": 27.10, "analyst": "تحلیل کارگزاری فارابی"},
                {"symbol": "وبملت", "name": "بانک ملت", "signal": "hold", "targetPrice": 18000, "currentPrice": 15200, "upside": 18.42, "analyst": "تحلیل کارگزاری آگاه"},
                {"symbol": "خودرو", "name": "ایران خودرو", "signal": "sell", "targetPrice": 2200, "currentPrice": 2750, "upside": -20.0, "analyst": "تحلیل کارگزاری بهمن"},
            ],
            market_status="open",
            analysis_date=datetime.now().isoformat(),
        ),
    )


class ProfitPredictionResponse(BaseModel):
    symbol: str
    fiscal_year: int
    predictions: list[dict[str, Any]]
    growth_rate: dict[str, float]
    current_eps: float
    predicted_eps: float
    revenue_forecast: list[dict[str, Any]]
    assumptions: list[str]
    risks: list[str]


class AnalysisSummaryResponse(BaseModel):
    market_status: str
    market_trend: str
    total_market_cap: int
    active_symbols: int
    avg_pe: float
    avg_dividend_yield: float
    index_change: dict[str, Any]
    index_hom_weight_change: dict[str, Any]
    market_participation: dict[str, Any]
    top_sectors: list[dict[str, Any]]
    analysis_date: str


@router.get("")
async def analysis_overview() -> ApiResponse[AnalysisSummaryResponse]:
    return ApiResponse[AnalysisSummaryResponse](
        success=True,
        data=AnalysisSummaryResponse(
            market_status="open",
            market_trend="bullish",
            total_market_cap=72_500_000_000_000_000,
            active_symbols=723,
            avg_pe=6.8,
            avg_dividend_yield=2.3,
            index_change={"value": 2547800, "change": 18250, "change_percent": 0.72},
            index_hom_weight_change={"value": 845200, "change": 4850, "change_percent": 0.58},
            market_participation={
                "buy_power": 58.3,
                "sell_power": 41.7,
                "individual_traders": 125000,
                "institutional_traders": 340,
            },
            top_sectors=[
                {"name": "فلزات اساسی", "change_percent": 1.82, "impact": 0.45},
                {"name": "فرآورده‌های نفتی", "change_percent": 1.15, "impact": 0.28},
                {"name": "بانکداری", "change_percent": 0.95, "impact": 0.19},
            ],
            analysis_date=date.today().isoformat(),
        ),
    )


@router.get("/sentiment")
async def market_sentiment() -> ApiResponse[SentimentResponse]:
    return ApiResponse[SentimentResponse](
        success=True,
        data=SentimentResponse(
            overall_sentiment="cautiously_bullish",
            sentiment_score=62.5,
            indicators={
                "news_sentiment": 58.0,
                "social_media_sentiment": 65.0,
                "institutional_sentiment": 72.0,
                "retail_sentiment": 55.0,
            },
            bullish_factors=[
                "افزایش قیمت دلار و اثر مثبت بر شرکت‌های صادراتی",
                "کاهش نرخ بهره بانکی",
                "گزارش‌های مناسب فصلی شرکت‌ها",
            ],
            bearish_factors=[
                "عدم قطعیت در بودجه ۱۴۰۴",
                "ریسک‌های سیاسی منطقه‌ای",
                "افزایش نرخ خوراک پتروشیمی‌ها",
            ],
            fear_greed_index=58,
            date=datetime.now().isoformat(),
        ),
    )


@router.get("/trends")
async def market_trends() -> ApiResponse[list[TrendResponse]]:
    trends = [
        TrendResponse(
            trend="صعودی",
            sector="فلزات اساسی",
            confidence=85,
            symbols=["فولاد", "ذوب", "اهرام", "کاوه"],
            reasons="افزایش قیمت جهانی سنگ آهن و فولاد",
        ),
        TrendResponse(
            trend="صعودی",
            sector="پالایشی",
            confidence=72,
            symbols=["شپنا", "شبریز", "شبندر", "شرانل"],
            reasons="افزایش قیمت نفت و حاشیه سود پالایش",
        ),
        TrendResponse(
            trend="خنثی",
            sector="بانکداری",
            confidence=55,
            symbols=["وبملت", "وتجارت", "وصندوق", "وبصادر"],
            reasons="ثبت صورت‌های مالی مناسب اما عدم رشد قابل توجه",
        ),
        TrendResponse(
            trend="نزولی",
            sector="خودرویی",
            confidence=68,
            symbols=["خودرو", "خساپا", "خگستر", "خبهمن"],
            reasons="عدم شفافیت در قیمت‌گذاری دستوری",
        ),
    ]
    return ApiResponse[list[TrendResponse]](success=True, data=trends)


@router.get("/recommendations")
async def market_recommendations() -> ApiResponse[list[RecommendationResponse]]:
    raw = [
        {"symbol": "فولاد", "action": "buy", "confidence": 85, "target_price": 52000, "stop_loss": 38000, "current_price": 42500, "reason": "قیمت جهانی فولاد صعودی و P/E جذاب", "timeframe": "میان‌مدت"},
        {"symbol": "شپنا", "action": "buy", "confidence": 72, "target_price": 68000, "stop_loss": 48000, "current_price": 53500, "reason": "افزایش حاشیه سود پالایش در فصل جاری", "timeframe": "کوتاه‌مدت"},
        {"symbol": "وبملت", "action": "hold", "confidence": 60, "target_price": 18000, "stop_loss": 12000, "current_price": 15200, "reason": "منتظر گزارش‌های فصلی آینده", "timeframe": "میان‌مدت"},
        {"symbol": "خودرو", "action": "sell", "confidence": 55, "target_price": None, "stop_loss": None, "current_price": 2750, "reason": "عدم شفافیت قیمت‌گذاری و زیان عملیاتی", "timeframe": "کوتاه‌مدت"},
    ]
    recommendations = []
    for r in raw:
        upside = None
        if r["target_price"] is not None and r["current_price"] and r["current_price"] != 0:
            upside = round((r["target_price"] - r["current_price"]) / r["current_price"] * 100, 2)
        recommendations.append(RecommendationResponse(upside=upside, **r))
    return ApiResponse[list[RecommendationResponse]](success=True, data=recommendations)


@router.get("/elliot-waves/{symbol}")
async def elliot_wave_analysis(symbol: str) -> ApiResponse[ElliotWaveResponse]:
    return ApiResponse[ElliotWaveResponse](
        success=True,
        data=ElliotWaveResponse(
            symbol=symbol,
            wave_count=5,
            current_wave=3,
            waves=[
                {"wave": 1, "type": "impulse", "start": 28000, "end": 35000, "percent": 25.0},
                {"wave": 2, "type": "corrective", "start": 35000, "end": 32000, "percent": -8.6},
                {"wave": 3, "type": "impulse", "start": 32000, "end": 48000, "percent": 50.0, "current": True},
                {"wave": 4, "type": "corrective", "start": 48000, "end": None, "percent": None, "projected": True},
                {"wave": 5, "type": "impulse", "start": None, "end": None, "percent": None, "projected": True},
            ],
            fibonacci_levels={"0.382": 41900, "0.5": 40000, "0.618": 38100, "1.0": 32000, "1.272": 28000, "1.618": 22000},
            target_price=55000,
            stop_loss=31000,
            pattern="impulsive",
            analysis="موج سوم در حال شکل‌گیری است و احتمال رسیدن به قیمت ۵۵,۰۰۰ تومان وجود دارد.",
        ),
    )


@router.get("/liquidity")
async def liquidity_flow() -> ApiResponse[LiquidityResponse]:
    return ApiResponse[LiquidityResponse](
        success=True,
        data=LiquidityResponse(
            date=date.today().isoformat(),
            total_trade_value=85_000_000_000_000,
            total_trade_volume=12_500_000_000,
            total_inflow=12_800_000_000_000,
            total_outflow=10_000_000_000_000,
            net_flow=2_800_000_000_000,
            institutional_flow=2_800_000_000_000,
            retail_flow=-2_800_000_000_000,
            top_inflow_sectors=[
                {"sector": "فلزات اساسی", "inflow": 4_500_000_000_000, "symbols": ["فولاد", "کاوه", "اهرم"]},
                {"sector": "شیمیایی", "inflow": 3_200_000_000_000, "symbols": ["شپنا", "شبندر"]},
                {"sector": "بانکی", "inflow": 2_100_000_000_000, "symbols": ["وبملت", "وتجارت"]},
            ],
            top_outflow_sectors=[
                {"sector": "خودرویی", "outflow": 1_800_000_000_000, "symbols": ["خودرو", "خگستر"]},
                {"sector": "سیمانی", "outflow": 900_000_000_000, "symbols": ["سیدکو", "ساربیل"]},
            ],
            money_flow_index=62.3,
            interpretation="پول‌های هوشمند در حال ورود به بازار و عمدتاً به سمت فلزات اساسی در حرکت است.",
        ),
    )


@router.get("/interest-rates")
async def interest_and_currency_rates() -> ApiResponse[InterestRateResponse]:
    return ApiResponse[InterestRateResponse](
        success=True,
        data=InterestRateResponse(
            date=date.today().isoformat(),
            interest_rates={
                "sana_rate": 23.5,
                "interbank_rate": 21.8,
                "deposit_rate": 18.0,
                "lending_rate": 25.0,
                "government_bond_yield": 28.5,
            },
            sana_rate=23.5,
            currency_rates={
                "usd_rial": {"open": 615000, "close": 623000, "change_percent": 1.3},
                "eur_rial": {"open": 668000, "close": 676000, "change_percent": 1.2},
                "gbp_rial": {"open": 780000, "close": 791000, "change_percent": 1.4},
                "aed_rial": {"open": 167500, "close": 169500, "change_percent": 1.19},
            },
            global_rates={
                "us_fed_rate": 5.5,
                "ecb_rate": 4.25,
                "uk_base_rate": 5.25,
                "gold_price_usd": 2340,
                "oil_price_brent": 85.3,
            },
            analysis="نرخ سندان با افزایش ۰.۳ درصدی همراه بوده و دلار در کانال ۶۲ هزار تومان تثبیت شده است.",
        ),
    )


@router.get("/profit-prediction/{symbol}")
async def profit_prediction(symbol: str) -> ApiResponse[ProfitPredictionResponse]:
    return ApiResponse[ProfitPredictionResponse](
        success=True,
        data=ProfitPredictionResponse(
            symbol=symbol,
            fiscal_year=1404,
            predictions=[
                {"year": 1404, "estimated_eps": 9850, "estimated_revenue": 185_000_000_000_000, "estimated_net_profit": 32_000_000_000_000, "confidence": 78, "pe_forward": 4.2},
                {"year": 1403, "estimated_eps": 8520, "estimated_revenue": 168_000_000_000_000, "estimated_net_profit": 28_000_000_000_000, "confidence": 85, "pe_forward": 4.8},
                {"year": 1402, "actual_eps": 7850, "actual_revenue": 152_000_000_000_000, "actual_net_profit": 25_500_000_000_000, "confidence": 100, "actual": True},
            ],
            growth_rate={"revenue_growth": 10.1, "profit_growth": 14.3},
            current_eps=7850.0,
            predicted_eps=9850.0,
            revenue_forecast=[
                {"year": 1402, "revenue": 152_000_000_000_000},
                {"year": 1403, "revenue": 168_000_000_000_000},
                {"year": 1404, "revenue": 185_000_000_000_000},
            ],
            assumptions=[
                "قیمت فروش محصول با نرخ دلار توافقی محاسبه شده است",
                "نرخ تورم ۳۰ درصدی برای هزینه‌ها در نظر گرفته شده است",
                "تولید با ۹۰ درصد ظرفیت اسمی انجام می‌شود",
            ],
            risks=[
                "کاهش قیمت‌های جهانی",
                "افزایش نرخ خوراک و انرژی",
                "تحریم‌های بین‌المللی",
            ],
        ),
    )
