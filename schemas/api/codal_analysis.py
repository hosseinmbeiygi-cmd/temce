from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AccountMappingRequest(BaseModel):
    label: str
    industry: str | None = None


class AccountMappingResponse(BaseModel):
    canonical_code: str | None = None
    canonical_name: str | None = None
    confidence: float = 0
    method: str = ""
    source_label: str = ""


class BatchMappingRequest(BaseModel):
    labels: list[str]
    industry: str | None = None


class BatchMappingResponse(BaseModel):
    results: list[AccountMappingResponse] = Field(default_factory=list)
    unmapped: list[str] = Field(default_factory=list)


class HorizontalAnalysisResponse(BaseModel):
    revenue_growth: float | None = None
    gross_profit_growth: float | None = None
    operating_profit_growth: float | None = None
    net_profit_growth: float | None = None
    total_assets_growth: float | None = None
    total_liabilities_growth: float | None = None
    equity_growth: float | None = None


class VerticalAnalysisResponse(BaseModel):
    pl_items: dict[str, float] = Field(default_factory=dict)
    bs_items: dict[str, float] = Field(default_factory=dict)


class RatioCategoryResponse(BaseModel):
    profitability: dict[str, float | None] = Field(default_factory=dict)
    liquidity: dict[str, float | None] = Field(default_factory=dict)
    leverage: dict[str, float | None] = Field(default_factory=dict)
    activity: dict[str, float | None] = Field(default_factory=dict)
    cash_flow: dict[str, float | None] = Field(default_factory=dict)


class DuPontResponse(BaseModel):
    net_profit_margin: float | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None
    roe: float | None = None
    roe_dupont: float | None = None


class EarningsQualityResponse(BaseModel):
    cash_conversion_ratio: float | None = None
    accruals_ratio: float | None = None
    receivables_growth_vs_revenue: float | None = None
    quality_score: float = 0
    warnings: list[str] = Field(default_factory=list)


class HealthScoreResponse(BaseModel):
    overall_score: float = 0
    classification: str = ""
    financial_strength: float = 0
    earnings_quality_score: float = 0
    liquidity_stability: float = 0
    leverage_risk: float = 0
    profitability: float = 0


class BenchmarkComparisonResponse(BaseModel):
    metric: str = ""
    company_value: float | None = None
    industry_median: float | None = None
    percentile: float | None = None
    status: str = ""


class BenchmarkResponse(BaseModel):
    industry: str = ""
    comparisons: list[BenchmarkComparisonResponse] = Field(default_factory=list)
    above_median_count: int = 0
    total_comparisons: int = 0


class ForensicResponse(BaseModel):
    overall_risk: float = 0
    benford_risk: float = 0
    ratio_anomaly_risk: float = 0
    warnings: list[str] = Field(default_factory=list)
    benford_mad: float | None = None
    benford_passing: bool | None = None


class NLPResponse(BaseModel):
    sentiment_score: float = 0
    optimism_score: float = 0
    uncertainty_score: float = 0
    risk_phrases: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    word_count: int = 0


class AuditorOpinionResponse(BaseModel):
    opinion_type: str = ""
    has_emphasis_of_matter: bool = False
    has_qualification: bool = False
    is_modified: bool = False
    key_paragraphs: list[str] = Field(default_factory=list)


class ReportSectionResponse(BaseModel):
    title: str = ""
    content: dict[str, Any] = Field(default_factory=dict)


class AlertResponse(BaseModel):
    type: str = ""
    severity: str = ""
    message: str = ""


class AnalysisReportResponse(BaseModel):
    symbol: str = ""
    fiscal_period: str = ""
    generated_at: str = ""
    overall_score: float = 0
    classification: str = ""
    analysis_status: str = ""
    sections: list[ReportSectionResponse] = Field(default_factory=list)
    alerts: list[AlertResponse] = Field(default_factory=list)


class ComprehensiveAnalysisResponse(BaseModel):
    symbol: str = ""
    fiscal_period: str = ""
    analysis_status: str = ""
    snapshot: dict[str, float] = Field(default_factory=dict)
    horizontal: HorizontalAnalysisResponse = Field(default_factory=HorizontalAnalysisResponse)
    vertical: VerticalAnalysisResponse = Field(default_factory=VerticalAnalysisResponse)
    ratios: RatioCategoryResponse = Field(default_factory=RatioCategoryResponse)
    dupont: DuPontResponse = Field(default_factory=DuPontResponse)
    earnings_quality: EarningsQualityResponse = Field(default_factory=EarningsQualityResponse)
    health_score: HealthScoreResponse = Field(default_factory=HealthScoreResponse)
    benchmark: BenchmarkResponse = Field(default_factory=BenchmarkResponse)
    forensic: ForensicResponse = Field(default_factory=ForensicResponse)
