from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

from core.logging import get_logger
from schemas.api.codal_analysis import (
    AccountMappingRequest,
    BatchMappingRequest,
)
from schemas.common.responses import ApiResponse
from services.codal_analysis.service import CodalProfessionalAnalysisService

logger = get_logger(__name__)

router = APIRouter()
analysis_service = CodalProfessionalAnalysisService()


@router.get("/{symbol}/comprehensive-analysis", summary="تحلیل جامع حرفه‌ای کدال")
async def comprehensive_analysis(
    symbol: str,
    industry: str | None = Query(None, description="صنعت برای مقایسه (پیش‌فرض: تولیدی)"),
) -> ApiResponse[dict[str, Any]]:
    """تحلیل جامع و حرفه‌ای یک نماد شامل تحلیل افقی، عمودی، نسبت‌ها، دوپونت، کیفیت سود، امتیازدهی و بنچمارک صنعت"""
    try:
        result = analysis_service.analyze_symbol(symbol, industry)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, data=result, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed comprehensive analysis for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/professional-report", summary="گزارش کارشناسی حرفه‌ای کدال")
async def professional_report(
    symbol: str,
    industry: str | None = Query(None, description="صنعت برای مقایسه"),
) -> ApiResponse[dict[str, Any]]:
    """تولید گزارش کارشناسی کامل و ساختاریافته شامل خلاصه اجرایی، تحلیل‌ها و هشدارها"""
    try:
        result = analysis_service.generate_professional_report(symbol, industry)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, data=result, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed professional report for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/ratios-extended", summary="نسبت‌های مالی گسترده")
async def ratios_extended(symbol: str) -> ApiResponse[dict[str, Any]]:
    """محاسبه مجموعه کامل نسبت‌های مالی (سودآوری، نقدینگی، اهرمی، فعالیت، جریان نقد)"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("ratios", {}))
    except Exception as exc:
        logger.exception("Failed ratios for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/dupont", summary="تحلیل دوپونت")
async def dupont(symbol: str) -> ApiResponse[dict[str, Any]]:
    """تحلیل دوپونت ROE شامل حاشیه سود خالص، گردش دارایی و ضریب اهرمی"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("dupont", {}))
    except Exception as exc:
        logger.exception("Failed DuPont analysis for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/earnings-quality", summary="تحلیل کیفیت سود")
async def earnings_quality(symbol: str) -> ApiResponse[dict[str, Any]]:
    """تحلیل کیفیت سود شامل نسبت تبدیل نقدی، نسبت اقلام تعهدی و هشدارهای کیفیت سود"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("earnings_quality", {}))
    except Exception as exc:
        logger.exception("Failed earnings quality for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/health-score", summary="امتیاز سلامت مالی")
async def health_score(symbol: str) -> ApiResponse[dict[str, Any]]:
    """امتیازدهی جامع سلامت مالی شامل امتیاز نهایی، طبقه‌بندی و مؤلفه‌ها"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("health_score", {}))
    except Exception as exc:
        logger.exception("Failed health score for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/benchmark", summary="مقایسه با صنعت")
async def benchmark(
    symbol: str,
    industry: str | None = Query(None, description="صنعت برای مقایسه"),
) -> ApiResponse[dict[str, Any]]:
    """مقایسه نسبت‌های مالی شرکت با میانگین صنعت و رتبه‌بندی درصدی"""
    try:
        result = analysis_service.analyze_symbol(symbol, industry)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("benchmark", {}))
    except Exception as exc:
        logger.exception("Failed benchmark for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/forensic", summary="تحلیل تقلب و ریسک")
async def forensic(symbol: str) -> ApiResponse[dict[str, Any]]:
    """تحلیل قانون بنفورد، تشخیص ناهنجاری و ارزیابی ریسک تقلب مالی"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("forensic", {}))
    except Exception as exc:
        logger.exception("Failed forensic for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/map-account", summary="نگاشت حساب به استاندارد")
async def map_account(req: AccountMappingRequest) -> ApiResponse[dict[str, Any]]:
    """نگاشت عنوان حساب فارسی به حساب استاندارد با امتیاز اطمینان"""
    try:
        result = analysis_service.map_account(req.label, req.industry)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed account mapping")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/batch-map-accounts", summary="نگاشت گروهی حساب‌ها")
async def batch_map_accounts(req: BatchMappingRequest) -> ApiResponse[dict[str, Any]]:
    """نگاشت گروهی عناوین حساب به حساب‌های استاندارد"""
    try:
        result = analysis_service.batch_map_accounts(req.labels, req.industry)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed batch account mapping")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/analyze-sentiment", summary="تحلیل متن گزارش مدیریت")
async def analyze_sentiment(text: str = Body(..., embed=True)) -> ApiResponse[dict[str, Any]]:
    """تحلیل احساسات و لحن گزارش تفسیری مدیریت با NLP"""
    try:
        result = analysis_service.analyze_sentiment(text)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed sentiment analysis")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/analyze-auditor", summary="تحلیل گزارش حسابرس")
async def analyze_auditor(text: str = Body(..., embed=True)) -> ApiResponse[dict[str, Any]]:
    """تحلیل و طبقه‌بندی نظر حسابرس مستقل"""
    try:
        result = analysis_service.analyze_auditor(text)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed auditor analysis")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/horizontal", summary="تحلیل افقی")
async def horizontal(symbol: str) -> ApiResponse[dict[str, Any]]:
    """تحلیل افقی (نرخ رشد) اقلام اصلی صورت‌های مالی"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("horizontal", {}))
    except Exception as exc:
        logger.exception("Failed horizontal analysis for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/vertical", summary="تحلیل عمودی")
async def vertical(symbol: str) -> ApiResponse[dict[str, Any]]:
    """تحلیل عمودی (درصدی از فروش و دارایی) صورت‌های مالی"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result.get("vertical", {}))
    except Exception as exc:
        logger.exception("Failed vertical analysis for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/audit-procedures", summary="رویه‌های تحلیلی حسابرسی (ISA 520)")
async def audit_procedures(symbol: str) -> ApiResponse[dict[str, Any]]:
    """اجرای رویه‌های تحلیلی حسابرسی شامل تحلیل روند و نسبت‌های غیرعادی طبق ISA 520"""
    try:
        result = analysis_service.analyze_symbol(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "audit_procedures": result.get("audit_procedures", []),
                "going_concern": result.get("going_concern", {}),
            },
        )
    except Exception as exc:
        logger.exception("Failed audit procedures for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/going-concern", summary="ارزیابی تداوم فعالیت (ISA 570)")
async def going_concern(symbol: str) -> ApiResponse[dict[str, Any]]:
    """ارزیابی تداوم فعالیت شرکت بر اساس ISA 570 و IAS 1"""
    try:
        result = analysis_service.audit_going_concern(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed going concern for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/semantic-map-account", summary="نگاشت هوشمند معنایی حساب")
async def semantic_map_account(req: AccountMappingRequest) -> ApiResponse[dict[str, Any]]:
    """نگاشت هوشمند عنوان حساب با استفاده از شباهت معنایی (Embedding-based) همراه با پیشنهادات جایگزین"""
    try:
        result = analysis_service.semantic_map_account(req.label, req.industry)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed semantic account mapping")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/semantic-batch-map", summary="نگاشت گروهی هوشمند حساب‌ها")
async def semantic_batch_map(req: BatchMappingRequest) -> ApiResponse[dict[str, Any]]:
    """نگاشت گروهی با تشخیص خودکار موارد نیازمند بررسی انسانی"""
    try:
        result = analysis_service.semantic_batch_map(req.labels, req.industry)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed semantic batch mapping")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/ifrs/lease-classify", summary="طبقه‌بندی اجاره (IFRS 16)")
async def ifrs_lease(
    annual_payment: float,
    lease_term: int,
    economic_life: int,
    asset_value: float,
    ownership_transfer: bool = False,
) -> ApiResponse[dict[str, Any]]:
    """طبقه‌بندی اجاره به مالی یا عملیاتی بر اساس IFRS 16"""
    try:
        result = analysis_service.ifrs_lease_classify(
            annual_payment, lease_term, economic_life, asset_value, ownership_transfer
        )
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed IFRS 16 lease classification")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/ifrs/revenue-recognition", summary="شناسایی درآمد (IFRS 15)")
async def ifrs_revenue(
    contract_price: float,
    obligations: int,
    standalone_prices: str | None = None,
) -> ApiResponse[dict[str, Any]]:
    """تحلیل ۵ مرحله‌ای شناسایی درآمد بر اساس IFRS 15"""
    try:
        prices = (
            [float(x.strip()) for x in (standalone_prices or "").split(",") if x.strip()] if standalone_prices else None
        )
        result = analysis_service.ifrs_revenue_recognition(contract_price, obligations, prices)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed IFRS 15 revenue recognition")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/impairment-test", summary="آزمون کاهش ارزش (IAS 36)")
async def impairment_test(
    carrying_amount: float,
    cashflows: str,
    fair_value: float | None = None,
) -> ApiResponse[dict[str, Any]]:
    """آزمون کاهش ارزش دارایی‌ها بر اساس IAS 36 با روش DCF"""
    try:
        cf_list = [float(x.strip()) for x in cashflows.split(",") if x.strip()]
        result = analysis_service.impairment_test(carrying_amount, cf_list, fair_value)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed impairment test")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/tax-reconciliation", summary="رسیدگی مالیاتی (IAS 12)")
async def tax_reconciliation(
    accounting_profit: float,
    permanent_additions: str = "",
) -> ApiResponse[dict[str, Any]]:
    """رسیدگی تفاوت‌های دائمی و موقتی مالیاتی بر اساس IAS 12"""
    try:
        additions = []
        if permanent_additions:
            for item in permanent_additions.split(";"):
                parts = item.split(":")
                if len(parts) == 2:
                    additions.append((parts[0].strip(), float(parts[1].strip())))
        result = analysis_service.tax_reconciliation(accounting_profit, additions)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed tax reconciliation")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 315 Risk Assessment ───────────────────────────────────────


@router.get("/{symbol}/risk-assessment", summary="ارزیابی ریسک حسابرسی (ISA 315)")
async def risk_assessment(symbol: str) -> ApiResponse[dict[str, Any]]:
    """ارزیابی ریسک در سطح صورت‌های مالی و ادعاهای حسابرسی طبق ISA 315"""
    try:
        result = analysis_service.audit_risk_assessment(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed risk assessment for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 320 Materiality ───────────────────────────────────────────


@router.get("/{symbol}/materiality", summary="محاسبه مادیت (ISA 320)")
async def materiality(symbol: str) -> ApiResponse[dict[str, Any]]:
    """محاسبه مادیت برنامه‌ریزی، مادیت اجرایی و آستانه کاملاً ناچیز طبق ISA 320"""
    try:
        result = analysis_service.audit_materiality(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed materiality for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 330 Control Testing ──────────────────────────────────────


@router.get("/{symbol}/control-testing", summary="تست کنترل‌ها (ISA 330)")
async def control_testing(symbol: str) -> ApiResponse[dict[str, Any]]:
    """ارزیابی کنترل‌های داخلی در چرخه‌های فروش، خرید، حقوق، خزانه و گزارشگری طبق ISA 330"""
    try:
        result = analysis_service.audit_control_testing(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed control testing for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/{symbol}/audit-program", summary="برنامه حسابرسی")
async def audit_program(
    symbol: str,
    accounts: str | None = Query(None, description="حساب‌های مورد نظر (جداسازی با کاما)"),
) -> ApiResponse[dict[str, Any]]:
    """تولید برنامه حسابرسی تفصیلی برای حساب‌های مختلف بر اساس ریسک‌های شناسایی شده"""
    try:
        specific = [a.strip() for a in accounts.split(",") if a.strip()] if accounts else None
        result = analysis_service.audit_generate_program(symbol, specific)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed audit program for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 450 Misstatement Evaluation ──────────────────────────────


@router.get("/{symbol}/misstatement-evaluation", summary="ارزیابی تحریف‌ها (ISA 450)")
async def misstatement_evaluation(symbol: str) -> ApiResponse[dict[str, Any]]:
    """ارزیابی تحریف‌های شناسایی شده (واقعی، برآوردی و تعمیم یافته) و تأثیر آن بر نظر حسابرس طبق ISA 450"""
    try:
        result = analysis_service.audit_misstatement_evaluation(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed misstatement evaluation for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/misstatement/add", summary="ثبت تحریف حسابرسی")
async def add_misstatement(
    symbol: str,
    reference: str,
    description: str,
    amount: float,
    category: str,
    account: str,
) -> ApiResponse[dict[str, Any]]:
    """ثبت یک تحریف حسابرسی (واقعی/برآوردی/تعمیم یافته) برای ارزیابی"""
    try:
        result = analysis_service.audit_add_misstatement(symbol, reference, description, amount, category, account)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed to add misstatement")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: Advanced Audit Sampling ──────────────────────────────────────


@router.post("/sampling/stratified", summary="نمونه‌گیری طبقه‌بندی شده")
async def sampling_stratified(items: list[dict[str, Any]]) -> ApiResponse[dict[str, Any]]:
    """نمونه‌گیری طبقه‌بندی شده برای آزمون محتوا"""
    try:
        result = analysis_service.audit_sampling_stratified(items)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed stratified sampling")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/sampling/attribute", summary="نمونه‌گیری صفت (ISA 530)")
async def sampling_attribute(
    population_size: int,
    expected_rate: float = 0.01,
    tolerable_rate: float = 0.05,
) -> ApiResponse[dict[str, Any]]:
    """نمونه‌گیری صفت برای تست کنترل‌ها طبق ISA 530"""
    try:
        result = analysis_service.audit_sampling_attribute(population_size, expected_rate, tolerable_rate)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed attribute sampling")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/sampling/classical-variables", summary="نمونه‌گیری کلاسیک متغیر")
async def sampling_classical(
    sample_values: list[float],
    book_values: list[float],
    population_size: int,
    population_value: float,
    tolerable: float,
) -> ApiResponse[dict[str, Any]]:
    """نمونه‌گیری کلاسیک متغیر (برآورد تفاوت) برای آزمون محتوا"""
    try:
        result = analysis_service.audit_sampling_classical(
            sample_values, book_values, population_size, population_value, tolerable
        )
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed classical variables sampling")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/sampling/pps", summary="نمونه‌گیری PPS (MUS)")
async def sampling_pps(
    items: list[dict[str, Any]],
    materiality: float,
) -> ApiResponse[dict[str, Any]]:
    """نمونه‌گیری PPS (Monetary Unit Sampling) برای آزمون محتوا"""
    try:
        result = analysis_service.audit_sampling_pps(items, materiality)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed PPS sampling")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 240 Fraud Detection ───────────────────────────────────────────


@router.get("/{symbol}/fraud-assessment", summary="تشخیص تقلب (ISA 240)")
async def fraud_assessment(symbol: str) -> ApiResponse[dict[str, Any]]:
    """ارزیابی جامع ریسک تقلب شامل مثلث تقلب، شاخص‌های فروش/دارایی/فساد و رویکرد تست ثبت‌های روزنامه طبق ISA 240"""
    try:
        result = analysis_service.audit_fraud_assessment(symbol)
        if "error" in result:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed fraud assessment for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 540 Accounting Estimates ───────────────────────────────────────


@router.post("/test-estimate-range", summary="آزمون برآوردهای حسابداری (ISA 540)")
async def test_estimate_range(
    point_estimate: float,
    low: float,
    high: float,
) -> ApiResponse[dict[str, Any]]:
    """آزمون دامنه برآوردهای حسابداری، حساسیت و سوگیری مدیریت طبق ISA 540"""
    try:
        result = analysis_service.audit_estimate_range(point_estimate, low, high)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed estimate range test")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/test-provision", summary="آزمون ذخایر حسابداری")
async def test_provision(
    provision_type: str,
    recorded: float,
    estimated_low: float,
    estimated_high: float,
) -> ApiResponse[dict[str, Any]]:
    """آزمون کفایت ذخایر (گارانتی، مطالبات مشکوک الوصول، بازنشستگی و ...)"""
    try:
        result = analysis_service.audit_provision_test(provision_type, recorded, estimated_low, estimated_high)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed provision test")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 550 Related Parties ────────────────────────────────────────────


@router.post("/related-parties", summary="اشخاص وابسته (ISA 550)")
async def related_parties(
    transactions: list[dict[str, Any]],
) -> ApiResponse[dict[str, Any]]:
    """ارزیابی معاملات اشخاص وابسته، قیمت‌گذاری و افشا طبق ISA 550"""
    try:
        result = analysis_service.audit_related_parties(transactions)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed related parties assessment")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 560 Subsequent Events ──────────────────────────────────────────


@router.post("/subsequent-events", summary="رویدادهای بعد از ترازنامه (ISA 560)")
async def subsequent_events(
    events: list[dict[str, Any]],
) -> ApiResponse[dict[str, Any]]:
    """طبقه‌بندی رویدادهای بعد از دوره مالی به تعدیلی/غیرتعدیلی طبق ISA 560 و IAS 10"""
    try:
        result = analysis_service.audit_subsequent_events(events)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed subsequent events assessment")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 700/705 Audit Opinion ──────────────────────────────────────────


@router.post("/form-opinion", summary="اظهارنظر حسابرسی (ISA 700/705)")
async def form_opinion(
    uncorrected_misstatements: float = 0,
    planning_materiality: float = 0,
) -> ApiResponse[dict[str, Any]]:
    """تعیین نوع اظهارنظر حسابرس (مقبول/مشروط/مردود/عدم اظهار) بر اساس ISA 700/705 و ISA 320"""
    try:
        result = analysis_service.audit_form_opinion(uncorrected_misstatements, planning_materiality)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed opinion formulation")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 230 Documentation ──────────────────────────────────────────────


@router.post("/create-audit-file", summary="پرونده حسابرسی (ISA 230)")
async def create_audit_file(entity: str, period: str) -> ApiResponse[dict[str, Any]]:
    """ایجاد ساختار پرونده حسابرسی با برگه‌های کاری طبق ISA 230"""
    try:
        result = analysis_service.audit_create_file(entity, period)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed to create audit file")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 300 Audit Planning ─────────────────────────────────────────────


@router.post("/audit-plan", summary="برنامه‌ریزی حسابرسی (ISA 300)")
async def audit_plan(entity: str, period: str) -> ApiResponse[dict[str, Any]]:
    """برنامه‌ریزی استراتژی حسابرسی، تعیین تیم، زمان‌بندی و پوشش طبق ISA 300"""
    try:
        result = analysis_service.audit_planning_strategy(entity, period)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed audit planning")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 500 Audit Evidence ──────────────────────────────────────────────


@router.post("/assess-evidence", summary="شواهد حسابرسی (ISA 500)")
async def assess_evidence(account: str, assertions: list[str]) -> ApiResponse[dict[str, Any]]:
    """ارزیابی کفایت و مناسب بودن شواهد حسابرسی برای هر ادعا طبق ISA 500"""
    try:
        result = analysis_service.audit_evidence_assessment(account, assertions)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed evidence assessment")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 505 External Confirmations ──────────────────────────────────────


@router.post("/confirmations", summary="تأییدیه‌های خارجی (ISA 505)")
async def confirmations(
    requests: list[dict[str, Any]],
    total_population: float = 0,
) -> ApiResponse[dict[str, Any]]:
    """مدیریت تأییدیه‌های خارجی (حساب‌های دریافتنی، پرداختنی و ...) طبق ISA 505"""
    try:
        result = analysis_service.audit_confirmations(requests, total_population)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed confirmations")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 580 Written Representations ─────────────────────────────────────


@router.post("/representation-letter", summary="نمایندگی مدیریت (ISA 580)")
async def representation_letter(
    entity: str,
    period: str,
    obtain_all: bool = True,
    date: str = "",
) -> ApiResponse[dict[str, Any]]:
    """ایجاد و اخذ نامه نمایندگی مدیریت طبق ISA 580 با ۱۴ بند استاندارد"""
    try:
        result = analysis_service.audit_obtain_representation(entity, period, obtain_all, date)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed representation letter")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 501 Specific Evidence ───────────────────────────────────────────


@router.post("/inventory-observation", summary="حضور در شمارش موجودی (ISA 501)")
async def inventory_observation(
    location: str,
    date: str,
    test_counts: int = 100,
    test_differences: int = 0,
) -> ApiResponse[dict[str, Any]]:
    """حضور در شمارش فیزیکی موجودی کالا و ارزیابی صحت شمارش طبق ISA 501"""
    try:
        result = analysis_service.audit_inventory_observation(location, date, test_counts, test_differences)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed inventory observation")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/litigation-assessment", summary="ارزیابی دعاوی قضایی (ISA 501)")
async def litigation_assessment(
    case_name: str,
    nature: str,
    claim_amount: float,
    likelihood: str = "possible",
) -> ApiResponse[dict[str, Any]]:
    """ارزیابی دعاوی قضایی و تعیین ذخیره/افشای مورد نیاز طبق ISA 501"""
    try:
        result = analysis_service.audit_litigation_assessment(case_name, nature, claim_amount, likelihood)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed litigation assessment")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/opening-balances", summary="مانده‌های افتتاحیه (ISA 510/501)")
async def opening_balances(
    prior_audited: bool = False,
    prior_opinion: str = "unmodified",
) -> ApiResponse[dict[str, Any]]:
    """ارزیابی مانده‌های افتتاحیه در اولین قرارداد حسابرسی طبق ISA 501"""
    try:
        result = analysis_service.audit_opening_balances(prior_audited, prior_opinion)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed opening balances assessment")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 220 Quality Control ─────────────────────────────────────────────


@router.get("/independence-check", summary="استقلال حسابرس (ISA 220)")
async def independence_check() -> ApiResponse[dict[str, Any]]:
    """بررسی استقلال تیم حسابرسی بر اساس آیین رفتار حرفه‌ای و ISA 220"""
    try:
        result = analysis_service.audit_independence_check()
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed independence check")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.post("/eqcr-review", summary="کنترل کیفیه قرارداد (ISA 220)")
async def eqcr_review(
    engagement_partner: str,
    eqcr_partner: str,
    date: str,
    findings: list[dict[str, Any]] | None = None,
) -> ApiResponse[dict[str, Any]]:
    """کنترل کیفیت قرارداد حسابرسی (EQCR) با ۱۴ قلم چک‌لیست طبق ISA 220"""
    try:
        result = analysis_service.audit_eqcr_review(engagement_partner, eqcr_partner, date, findings)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed EQCR review")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ── NEW: ISA 260 Governance Communication ────────────────────────────────────


@router.post("/governance-communication", summary="ارتباط با حاکمیت (ISA 260)")
async def governance_communication(entity: str, period: str) -> ApiResponse[dict[str, Any]]:
    """برنامه ارتباط با ارکان حاکمیت شامل ۱۵ قلم ارتباطی و ۴ جلسه کمیته حسابرسی طبق ISA 260"""
    try:
        result = analysis_service.audit_governance_plan(entity, period)
        return ApiResponse[dict[str, Any]](success=True, data=result)
    except Exception as exc:
        logger.exception("Failed governance communication")
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})
