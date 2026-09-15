from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.codal_accounting_service import (
    _classify_item,
    _extract_last_value,
)
from services.codal_accounting_service import (
    list_reports as fs_list_reports,
)
from services.codal_accounting_service import (
    parse_report as fs_parse_report,
)
from services.codal_analysis.account_mapper import AccountMapper
from services.codal_analysis.analysis_engine import (
    analyze,
    build_snapshot,
)
from services.codal_analysis.audit_confirmations import ConfirmationManager, format_confirmation_for_response
from services.codal_analysis.audit_control_testing import (
    AuditProgramGenerator,
    ControlTester,
    format_audit_program_for_response,
    format_control_testing_for_response,
)
from services.codal_analysis.audit_documentation import AuditDocumenter, format_documentation_for_response
from services.codal_analysis.audit_estimates import EstimatesAuditor, format_estimates_for_response
from services.codal_analysis.audit_evidence import EvidenceEvaluator, format_evidence_for_response
from services.codal_analysis.audit_fraud import FraudAssessor, format_fraud_for_response
from services.codal_analysis.audit_governance_communication import (
    GovernanceCommunicator,
    format_governance_for_response,
)
from services.codal_analysis.audit_materiality import MaterialityCalculator, format_materiality_for_response
from services.codal_analysis.audit_misstatement import MisstatementEvaluator, format_misstatements_for_response
from services.codal_analysis.audit_opinion import OpinionFormulator, format_opinion_for_response
from services.codal_analysis.audit_planning import AuditPlanner, format_planning_for_response
from services.codal_analysis.audit_quality_control import QualityControlManager, format_qc_for_response
from services.codal_analysis.audit_related_parties import RelatedPartyAuditor, format_rp_for_response
from services.codal_analysis.audit_representations import RepresentationManager, format_representation_for_response
from services.codal_analysis.audit_risk_assessment import AuditRiskAssessor, format_risks_for_response
from services.codal_analysis.audit_sampling import (
    AttributeSampler,
    ClassicalVariablesSampler,
    PPSampler,
    StratifiedSampler,
    format_sampling_for_response,
)
from services.codal_analysis.audit_specific_evidence import (
    SpecificEvidenceAssessor,
    format_specific_evidence_for_response,
)
from services.codal_analysis.audit_subsequent_events import SubsequentEventsAuditor, format_subsequent_for_response
from services.codal_analysis.audit_workflow import AnalyticalReview, ProfessionalAuditWorkflow
from services.codal_analysis.benchmark import compare_with_industry
from services.codal_analysis.forensic import assess_fraud_risk
from services.codal_analysis.ifrs_compliance import IFRSComplianceEngine, IFRSDisclosureChecker
from services.codal_analysis.judgment_simulator import ProfessionalJudgmentSimulator
from services.codal_analysis.nlp_analyzer import analyze_auditor_opinion, analyze_management_report
from services.codal_analysis.report_generator import generate_report
from services.codal_analysis.scoring import compute_health_score
from services.codal_analysis.semantic_mapper import SemanticAccountMapper
from services.codal_analysis.validation import DataValidationPipeline

logger = get_logger(__name__)


class CodalProfessionalAnalysisService:
    def __init__(self):
        self.account_mapper = AccountMapper()
        self.semantic_mapper = SemanticAccountMapper()
        self.validation_pipeline = DataValidationPipeline()
        self.audit_workflow = ProfessionalAuditWorkflow()
        self.analytical_review = AnalyticalReview()
        self.ifrs_engine = IFRSComplianceEngine()
        self.ifrs_disclosure = IFRSDisclosureChecker()
        self.judgment_simulator = ProfessionalJudgmentSimulator()
        self.risk_assessor = AuditRiskAssessor()
        self.materiality_calculator = MaterialityCalculator()
        self.control_tester = ControlTester()
        self.audit_program_generator = AuditProgramGenerator()
        self.misstatement_evaluator = MisstatementEvaluator()
        self.stratified_sampler = StratifiedSampler()
        self.attribute_sampler = AttributeSampler()
        self.classical_sampler = ClassicalVariablesSampler()
        self.pps_sampler = PPSampler()
        self.fraud_assessor = FraudAssessor()
        self.estimates_auditor = EstimatesAuditor()
        self.rp_auditor = RelatedPartyAuditor()
        self.subsequent_auditor = SubsequentEventsAuditor()
        self.opinion_formulator = OpinionFormulator()
        self.audit_documenter = AuditDocumenter()
        self.audit_planner = AuditPlanner()
        self.evidence_evaluator = EvidenceEvaluator()
        self.confirmation_manager = ConfirmationManager()
        self.representation_manager = RepresentationManager()
        self.specific_evidence = SpecificEvidenceAssessor()
        self.qc_manager = QualityControlManager()
        self.governance_communicator = GovernanceCommunicator()

    def _load_classified_data(self, symbol: str) -> dict[str, Any]:
        reports = fs_list_reports(symbol)
        if not reports:
            return {"error": "No reports found", "analysis_status": "failed"}

        classified: dict[str, float] = {}
        seen_labels: set[str] = set()
        latest_report = None
        all_reports_by_type: dict[str, list[dict[str, Any]]] = {}

        for rt in {r["report_type"] for r in reports if r["report_type"]}:
            type_reports = [r for r in reports if r["report_type"] == rt]
            if not type_reports:
                continue
            all_reports_by_type[rt] = type_reports
            parsed = fs_parse_report(type_reports[0]["filepath"])
            if not parsed or "error" in parsed:
                continue
            if latest_report is None:
                latest_report = type_reports[0]

            for table in parsed.get("tables", []):
                for item in table.get("items", []):
                    label = item["label"]
                    if label in seen_labels:
                        continue
                    category = _classify_item(label)
                    if category:
                        seen_labels.add(label)
                        value = _extract_last_value(item)
                        if value != 0:
                            if category not in classified or abs(value) > abs(classified[category]):
                                classified[category] = value

        if not classified:
            return {"error": "No financial data could be classified", "analysis_status": "failed"}

        validated = self.validation_pipeline.reconcile(classified)
        return {
            "classified": classified,
            "validated": validated,
            "latest_report": latest_report,
            "all_reports": all_reports_by_type,
        }

    def analyze_symbol(self, symbol: str, industry: str | None = None) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}

        classified = loaded["classified"]
        validated = loaded["validated"]
        latest_report = loaded["latest_report"]

        snap = build_snapshot(validated, symbol=symbol, period=latest_report.get("date", "") if latest_report else "")
        analysis = analyze(snap)
        health = compute_health_score(analysis)
        benchmark = (
            compare_with_industry(analysis, industry or "تولیدی")
            if industry
            else compare_with_industry(analysis, "تولیدی")
        )

        classified_values = [v for v in classified.values() if v != 0]
        ratio_vals = {
            "roe": analysis.ratios.profitability.get("roe"),
            "roa": analysis.ratios.profitability.get("roa"),
            "debt_to_equity": analysis.ratios.leverage.get("debt_to_equity"),
            "current_ratio": analysis.ratios.liquidity.get("current_ratio"),
        }
        forensic = assess_fraud_risk(classified_values, ratio_vals)

        audit_procedures = self.audit_workflow.perform_analytical_procedures(snap, snap.prev)
        going_concern = self.audit_workflow.going_concern_assessment(
            snap, consecutive_loss_years=1 if snap.net_profit < 0 else 0
        )

        return {
            "symbol": symbol,
            "fiscal_period": snap.fiscal_period,
            "analysis_status": "full",
            "snapshot": {k: v for k, v in validated.items() if not k.startswith("_")},
            "validation": validated.get("_validation", {}),
            "horizontal": {
                "revenue_growth": analysis.horizontal.revenue_growth,
                "gross_profit_growth": analysis.horizontal.gross_profit_growth,
                "operating_profit_growth": analysis.horizontal.operating_profit_growth,
                "net_profit_growth": analysis.horizontal.net_profit_growth,
                "total_assets_growth": analysis.horizontal.total_assets_growth,
                "total_liabilities_growth": analysis.horizontal.total_liabilities_growth,
                "equity_growth": analysis.horizontal.equity_growth,
            },
            "vertical": {
                "pl_items": analysis.vertical.pl_items,
                "bs_items": analysis.vertical.bs_items,
            },
            "ratios": {
                "profitability": {k: _safe(v) for k, v in analysis.ratios.profitability.items()},
                "liquidity": {k: _safe(v) for k, v in analysis.ratios.liquidity.items()},
                "leverage": {k: _safe(v) for k, v in analysis.ratios.leverage.items()},
                "activity": {k: _safe(v) for k, v in analysis.ratios.activity.items()},
                "cash_flow": {k: _safe(v) for k, v in analysis.ratios.cash_flow.items()},
            },
            "dupont": {
                "net_profit_margin": _safe(analysis.dupont.net_profit_margin),
                "asset_turnover": _safe(analysis.dupont.asset_turnover),
                "equity_multiplier": _safe(analysis.dupont.equity_multiplier),
                "roe": _safe(analysis.dupont.roe),
                "roe_dupont": _safe(analysis.dupont.roe_dupont),
            },
            "earnings_quality": {
                "cash_conversion_ratio": _safe(analysis.earnings_quality.cash_conversion_ratio),
                "accruals_ratio": _safe(analysis.earnings_quality.accruals_ratio),
                "quality_score": analysis.earnings_quality.quality_score,
                "warnings": analysis.earnings_quality.warnings,
            },
            "health_score": {
                "overall_score": health.overall_score,
                "classification": health.classification,
                "financial_strength": health.financial_strength,
                "earnings_quality_score": health.earnings_quality,
                "liquidity_stability": health.liquidity_stability,
                "leverage_risk": health.leverage_risk,
                "profitability": health.profitability,
            },
            "benchmark": {
                "industry": benchmark.industry,
                "comparisons": [
                    {
                        "metric": c.metric,
                        "company_value": _safe(c.company_value),
                        "industry_median": _safe(c.industry_median),
                        "percentile": c.percentile,
                        "status": c.status,
                    }
                    for c in benchmark.comparisons
                ],
                "above_median_count": benchmark.above_median_count,
                "total_comparisons": benchmark.total_comparisons,
            },
            "forensic": {
                "overall_risk": forensic.overall_risk,
                "benford_risk": forensic.benford_risk,
                "ratio_anomaly_risk": forensic.ratio_anomaly_risk,
                "warnings": forensic.warnings,
            },
            "audit_procedures": [
                {
                    "procedure_name": p.procedure_name,
                    "status": p.status,
                    "deviation": _safe(p.deviation),
                    "conclusion": p.conclusion,
                    "risk_level": p.risk_level,
                }
                for p in audit_procedures
            ],
            "going_concern": {
                "status": going_concern.status,
                "risk_level": going_concern.risk_level,
                "indicators": going_concern.indicators,
                "current_ratio": going_concern.current_ratio,
                "negative_equity": going_concern.negative_equity,
            },
        }

    def generate_professional_report(self, symbol: str, industry: str | None = None) -> dict[str, Any]:
        analysis_data = self.analyze_symbol(symbol, industry)
        if "error" in analysis_data:
            return analysis_data

        snap = build_snapshot(
            dict(analysis_data.get("snapshot", {}).items()),
            symbol=symbol,
            period=analysis_data.get("fiscal_period", ""),
        )

        ca = analyze(snap)
        report = generate_report(ca)
        return {
            "symbol": report.symbol,
            "fiscal_period": report.fiscal_period,
            "generated_at": report.generated_at,
            "overall_score": report.overall_score,
            "classification": report.classification,
            "analysis_status": report.analysis_status,
            "sections": {s.title: s.content for s in report.sections},
            "alerts": [{"type": a["type"], "severity": a["severity"], "message": a["message"]} for a in report.alerts],
        }

    def analyze_sentiment(self, text: str) -> dict[str, Any]:
        result = analyze_management_report(text)
        return {
            "sentiment_score": result.sentiment_score,
            "optimism_score": result.optimism_score,
            "uncertainty_score": result.uncertainty_score,
            "risk_phrases": result.risk_phrases_found,
            "topics": result.topics,
            "word_count": result.word_count,
        }

    def analyze_auditor(self, text: str) -> dict[str, Any]:
        result = analyze_auditor_opinion(text)
        return {
            "opinion_type": result.opinion_type,
            "has_emphasis_of_matter": result.has_emphasis_of_matter,
            "has_qualification": result.has_qualification,
            "is_modified": result.is_modified,
            "key_paragraphs": result.key_paragraphs,
        }

    def map_account(self, label: str, industry: str | None = None) -> dict[str, Any]:
        result = self.account_mapper.map(label, industry)
        return {
            "canonical_code": result.canonical_code,
            "canonical_name": result.canonical_name,
            "confidence": result.confidence,
            "method": result.method,
            "source_label": result.source_label,
        }

    def batch_map_accounts(self, labels: list[str], industry: str | None = None) -> dict[str, Any]:
        results = self.account_mapper.batch_map(labels, industry)
        unmapped = self.account_mapper.get_unmapped(labels, industry)
        return {
            "results": [
                {
                    "canonical_code": r.canonical_code,
                    "canonical_name": r.canonical_name,
                    "confidence": r.confidence,
                    "method": r.method,
                    "source_label": r.source_label,
                }
                for r in results
            ],
            "unmapped": unmapped,
        }

    def semantic_map_account(self, label: str, industry: str | None = None) -> dict[str, Any]:
        result = self.semantic_mapper.map(label, industry)
        return {
            "canonical_code": result.canonical_code,
            "canonical_name": result.canonical_name,
            "confidence": result.confidence,
            "method": result.method,
            "source_label": result.source_label,
            "alternative_matches": result.alternative_matches,
            "needs_review": result.needs_review,
        }

    def semantic_batch_map(self, labels: list[str], industry: str | None = None) -> dict[str, Any]:
        results = self.semantic_mapper.batch_map(labels, industry)
        review_queue = self.semantic_mapper.get_review_queue(labels, industry)
        return {
            "results": [
                {
                    "canonical_code": r.canonical_code,
                    "canonical_name": r.canonical_name,
                    "confidence": r.confidence,
                    "method": r.method,
                    "source_label": r.source_label,
                    "needs_review": r.needs_review,
                }
                for r in results
            ],
            "review_queue": [
                {"source_label": r.source_label, "confidence": r.confidence, "alternatives": r.alternative_matches}
                for r in review_queue
            ],
        }

    def ifrs_lease_classify(
        self,
        annual_payment: float,
        lease_term: int,
        economic_life: int,
        asset_value: float,
        ownership_transfer: bool = False,
    ) -> dict[str, Any]:
        result = self.ifrs_engine.lease_classification(
            annual_payment, lease_term, economic_life, asset_value, ownership_transfer
        )
        return {
            "classification": result.classification,
            "right_of_use_asset": result.right_of_use_asset,
            "lease_liability": result.lease_liability,
            "annual_depreciation": result.annual_depreciation,
            "present_value": result.present_value,
            "reasoning": result.reasoning,
        }

    def ifrs_revenue_recognition(
        self, contract_price: float, obligations: int, standalone_prices: list[float] | None = None
    ) -> dict[str, Any]:
        result = self.ifrs_engine.revenue_recognition(contract_price, obligations, standalone_prices)
        return {
            "performance_obligations": result.performance_obligations,
            "transaction_price": result.transaction_price,
            "allocated_prices": result.allocated_prices,
            "timing": result.timing_of_recognition,
            "steps_completed": result.steps_completed,
            "reasoning": result.reasoning,
        }

    def impairment_test(
        self,
        carrying_amount: float,
        projected_cashflows: list[float],
        fair_value: float | None = None,
    ) -> dict[str, Any]:
        result = self.judgment_simulator.impairment_testing(carrying_amount, projected_cashflows, fair_value)
        return {
            "carrying_amount": result.carrying_amount,
            "recoverable_amount": result.recoverable_amount,
            "impairment_loss": result.impairment_loss,
            "is_impaired": result.is_impaired,
            "value_in_use": result.value_in_use,
            "fair_value_less_costs": result.fair_value_less_costs,
            "reasoning": result.reasoning,
        }

    def tax_reconciliation(
        self, accounting_profit: float, permanent_additions: list[tuple[str, float]] | None = None
    ) -> dict[str, Any]:
        result = self.judgment_simulator.tax_reconciliation(accounting_profit, permanent_additions)
        return {
            "accounting_profit": result.accounting_profit,
            "taxable_profit": result.taxable_profit,
            "current_tax": result.current_tax,
            "deferred_tax": result.deferred_tax,
            "effective_tax_rate": result.effective_tax_rate,
            "reconciliation_items": result.reconciliation_items,
        }

    def audit_going_concern(self, symbol: str) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        snap = build_snapshot(loaded["validated"], symbol=symbol)
        result = self.audit_workflow.going_concern_assessment(
            snap, consecutive_loss_years=1 if snap.net_profit < 0 else 0
        )
        return {
            "status": result.status,
            "risk_level": result.risk_level,
            "indicators": result.indicators,
            "current_ratio": result.current_ratio,
            "negative_equity": result.negative_equity,
            "consecutive_losses": result.consecutive_losses,
        }

    # ── ISA 315: Risk Assessment ───────────────────────────────────────

    def audit_risk_assessment(self, symbol: str) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        snap = build_snapshot(loaded["validated"], symbol=symbol)
        assessment = self.risk_assessor.assess_all(snap)
        return format_risks_for_response(assessment)

    # ── ISA 320: Materiality ───────────────────────────────────────────

    def audit_materiality(self, symbol: str) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        snap = build_snapshot(loaded["validated"], symbol=symbol)
        mat = self.materiality_calculator.assess_all(snap)
        return format_materiality_for_response(mat)

    # ── ISA 330: Control Testing ───────────────────────────────────────

    def audit_control_testing(self, symbol: str) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        build_snapshot(loaded["validated"], symbol=symbol)
        assessment = self.control_tester.assess_all_cycles()
        return format_control_testing_for_response(assessment)

    def audit_generate_program(
        self,
        symbol: str,
        specific_accounts: list[str] | None = None,
    ) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        snap = build_snapshot(loaded["validated"], symbol=symbol)
        assessment = self.risk_assessor.assess_all(snap)

        accounts = specific_accounts or [
            "revenue",
            "receivables",
            "inventory",
            "property_plant_equipment",
            "payables",
            "cash_and_equivalents",
            "equity",
        ]
        risk_levels: dict[str, str] = {}
        for acc in accounts:
            profile = assessment.account_risk_profiles.get(acc)
            risk_levels[acc] = profile.overall_risk_level if profile else "medium"

        programs = self.audit_program_generator.generate_full_audit_program(accounts, risk_levels)
        return format_audit_program_for_response(programs)

    # ── ISA 450: Misstatement Evaluation ───────────────────────────────

    def audit_misstatement_evaluation(self, symbol: str) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        snap = build_snapshot(loaded["validated"], symbol=symbol)
        mat = self.materiality_calculator.assess_all(snap)
        evaluation = self.misstatement_evaluator.evaluate(mat.planning_materiality, mat.performance_materiality)
        return format_misstatements_for_response(evaluation)

    def audit_add_misstatement(
        self,
        symbol: str,
        reference: str,
        description: str,
        amount: float,
        category: str,
        account: str,
    ) -> dict[str, Any]:
        ms = self.misstatement_evaluator.record_misstatement(reference, description, amount, category, account)
        return {
            "reference": ms.reference,
            "description": ms.description,
            "amount": ms.amount,
            "category": ms.category,
            "account": ms.account,
        }

    # ── Sampling ───────────────────────────────────────────────────────

    def audit_sampling_stratified(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        result = self.stratified_sampler.sample_all(items)
        return format_sampling_for_response(result)

    def audit_sampling_attribute(
        self,
        population_size: int,
        expected_rate: float,
        tolerable_rate: float,
    ) -> dict[str, Any]:
        # Simulate the test with 0 deviations found
        result = self.attribute_sampler.evaluate_results(
            sample_size=max(25, int(population_size * 0.1)),
            deviations_found=0,
            tolerance_rate=tolerable_rate,
        )
        return format_sampling_for_response(result)

    def audit_sampling_classical(
        self,
        sample_values: list[float],
        book_values: list[float],
        population_size: int,
        population_value: float,
        tolerable: float,
    ) -> dict[str, Any]:
        result = self.classical_sampler.evaluate_results(
            sample_values, book_values, population_size, population_value, tolerable
        )
        return format_sampling_for_response(result)

    def audit_sampling_pps(self, items: list[dict[str, Any]], materiality: float) -> dict[str, Any]:
        selected = self.pps_sampler.select_sample(items, materiality=materiality)
        return {
            "method": "PPS / Monetary Unit Sampling",
            "total_items": len(items),
            "sample_size": len(selected),
            "selected_items": selected,
        }

    # ── NEW: ISA 240 Fraud Detection ──────────────────────────────────

    def audit_fraud_assessment(self, symbol: str) -> dict[str, Any]:
        loaded = self._load_classified_data(symbol)
        if "error" in loaded:
            return {"symbol": symbol, **loaded}
        snap = build_snapshot(loaded["validated"], symbol=symbol)
        assessment = self.fraud_assessor.assess_all(snap)
        return format_fraud_for_response(assessment)

    # ── NEW: ISA 540 Accounting Estimates ────────────────────────────

    def audit_estimate_range(
        self,
        point_estimate: float,
        low: float,
        high: float,
    ) -> dict[str, Any]:
        result = self.estimates_auditor.test_range(point_estimate, low, high)
        return format_estimates_for_response(result)

    def audit_provision_test(
        self,
        provision_type: str,
        recorded: float,
        estimated_low: float,
        estimated_high: float,
    ) -> dict[str, Any]:
        result = self.estimates_auditor.test_provision(provision_type, recorded, estimated_low, estimated_high)
        return format_estimates_for_response([result])

    # ── NEW: ISA 550 Related Parties ─────────────────────────────────

    def audit_related_parties(
        self,
        transactions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        assessment = self.rp_auditor.assess(transactions)
        return format_rp_for_response(assessment)

    # ── NEW: ISA 560 Subsequent Events ───────────────────────────────

    def audit_subsequent_events(
        self,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        assessment = self.subsequent_auditor.assess(events)
        return format_subsequent_for_response(assessment)

    # ── NEW: ISA 700/705 Opinion Formulation ─────────────────────────

    def audit_form_opinion(
        self,
        uncorrected_misstatements: float = 0,
        planning_materiality: float = 0,
    ) -> dict[str, Any]:
        opinion = self.opinion_formulator.form_opinion(
            uncorrected_misstatements=uncorrected_misstatements,
            planning_materiality=planning_materiality,
        )
        return format_opinion_for_response(opinion)

    # ── NEW: ISA 230 Documentation ───────────────────────────────────

    def audit_create_file(self, entity: str, period: str) -> dict[str, Any]:
        af = self.audit_documenter.create_audit_file(entity, period)
        return format_documentation_for_response(af)

    # ── NEW: ISA 300 Audit Planning ──────────────────────────────────

    def audit_planning_strategy(self, entity: str, period: str) -> dict[str, Any]:
        strategy = self.audit_planner.create_strategy(entity, period)
        return format_planning_for_response(strategy)

    # ── NEW: ISA 500 Audit Evidence ──────────────────────────────────

    def audit_evidence_assessment(self, account: str, assertions: list[str]) -> dict[str, Any]:
        ec = self.evidence_evaluator.assess_evidence(account, assertions)
        return format_evidence_for_response(ec)

    # ── NEW: ISA 505 External Confirmations ─────────────────────────

    def audit_confirmations(self, requests: list[dict[str, Any]], total_population: float = 0) -> dict[str, Any]:
        confirm_reqs = []
        for r in requests:
            cr = self.confirmation_manager.create_request(
                r["entity"], r["account_type"], r["balance"], r.get("method", "positive")
            )
            if r.get("confirmed_balance") is not None:
                self.confirmation_manager.record_response(cr, r["confirmed_balance"], r.get("notes", ""))
            confirm_reqs.append(cr)
        summary = self.confirmation_manager.summarize(confirm_reqs, total_population)
        return format_confirmation_for_response(summary, confirm_reqs)

    # ── NEW: ISA 580 Written Representations ───────────────────────

    def audit_representation_letter(self, entity: str, period: str) -> dict[str, Any]:
        letter = self.representation_manager.create_letter(entity, period)
        self.representation_manager.check_completeness(letter)
        return format_representation_for_response(letter)

    def audit_obtain_representation(
        self, entity: str, period: str, obtain_all: bool = True, date: str = ""
    ) -> dict[str, Any]:
        letter = self.representation_manager.create_letter(entity, period)
        if obtain_all:
            self.representation_manager.obtain_all(letter, date)
        self.representation_manager.check_completeness(letter)
        return format_representation_for_response(letter)

    # ── NEW: ISA 501 Specific Evidence ─────────────────────────────

    def audit_inventory_observation(
        self, location: str, date: str, test_counts: int = 100, test_differences: int = 0
    ) -> dict[str, Any]:
        result = self.specific_evidence.inventory_observation(location, date, test_counts, test_differences)
        return format_specific_evidence_for_response(result)

    def audit_litigation_assessment(
        self, case_name: str, nature: str, claim_amount: float, likelihood: str = "possible"
    ) -> dict[str, Any]:
        result = self.specific_evidence.litigation_assessment(case_name, nature, claim_amount, likelihood)
        return format_specific_evidence_for_response(result)

    def audit_opening_balances(self, prior_audited: bool = False, prior_opinion: str = "unmodified") -> dict[str, Any]:
        result = self.specific_evidence.opening_balances(prior_audited, prior_opinion)
        return format_specific_evidence_for_response(result)

    # ── NEW: ISA 220 Quality Control ──────────────────────────────

    def audit_independence_check(self) -> dict[str, Any]:
        ic = self.qc_manager.check_independence()
        return format_qc_for_response(ic)

    def audit_eqcr_review(
        self, engagement_partner: str, eqcr_partner: str, date: str, findings: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        review = self.qc_manager.eqc_review(engagement_partner, eqcr_partner, date, findings)
        return format_qc_for_response(review)

    # ── NEW: ISA 260 Governance Communication ─────────────────────

    def audit_governance_plan(self, entity: str, period: str) -> dict[str, Any]:
        plan = self.governance_communicator.create_plan(entity, period)
        self.governance_communicator.check_completeness(plan)
        return format_governance_for_response(plan)


def _safe(val: float | None) -> float | None:
    if val is None:
        return None
    if val in (float("inf"), float("-inf")):
        return None
    return round(val, 4)
