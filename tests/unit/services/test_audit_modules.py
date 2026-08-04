from __future__ import annotations

from services.codal_analysis.analysis_engine import FinancialSnapshot
from services.codal_analysis.audit_confirmations import (
    ConfirmationManager,
    format_confirmation_for_response,
)
from services.codal_analysis.audit_control_testing import (
    AuditProgramGenerator,
    ControlTester,
    _attribute_sampling_sample_size,
    format_audit_program_for_response,
    format_control_testing_for_response,
)
from services.codal_analysis.audit_documentation import (
    AuditDocumenter,
    format_documentation_for_response,
)
from services.codal_analysis.audit_estimates import (
    EstimatesAuditor,
)
from services.codal_analysis.audit_evidence import (
    EvidenceEvaluator,
    format_evidence_for_response,
)
from services.codal_analysis.audit_fraud import (
    ASSET_FRAUD_INDICATORS,
    REVENUE_FRAUD_INDICATORS,
    FraudAssessor,
    format_fraud_for_response,
)
from services.codal_analysis.audit_governance_communication import (
    GovernanceCommunicator,
    format_governance_for_response,
)
from services.codal_analysis.audit_materiality import (
    MaterialityCalculator,
    format_materiality_for_response,
)
from services.codal_analysis.audit_misstatement import (
    MisstatementEvaluator,
    format_misstatements_for_response,
)
from services.codal_analysis.audit_opinion import (
    OpinionFormulator,
)
from services.codal_analysis.audit_planning import (
    AuditPlanner,
)
from services.codal_analysis.audit_quality_control import (
    QualityControlManager,
    format_qc_for_response,
)
from services.codal_analysis.audit_related_parties import (
    RelatedPartyAuditor,
)
from services.codal_analysis.audit_representations import (
    RepresentationManager,
    format_representation_for_response,
)
from services.codal_analysis.audit_risk_assessment import (
    AccountRiskProfile,
    AssertionRisk,
    AuditRiskAssessor,
    format_risks_for_response,
)
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
from services.codal_analysis.audit_subsequent_events import (
    SubsequentEventsAuditor,
)


def _make_snap(**overrides) -> FinancialSnapshot:
    data = {
        "revenue": 1_000_000,
        "cost_of_goods_sold": 600_000,
        "gross_profit": 400_000,
        "operating_expenses": 150_000,
        "operating_profit": 250_000,
        "financial_cost": 30_000,
        "financial_income": 5_000,
        "net_profit": 200_000,
        "eps": 500,
        "current_assets": 800_000,
        "non_current_assets": 1_200_000,
        "total_assets": 2_000_000,
        "current_liabilities": 400_000,
        "non_current_liabilities": 600_000,
        "total_liabilities": 1_000_000,
        "equity": 1_000_000,
        "total_equity": 1_000_000,
        "inventory": 300_000,
        "cash": 150_000,
        "accounts_receivable": 250_000,
        "accounts_payable": 200_000,
        "operating_cash_flow": 180_000,
        "investing_cash_flow": -100_000,
        "financing_cash_flow": -50_000,
        "capital": 500_000,
        "retained_earnings": 500_000,
        "depreciation": 80_000,
        "net_fixed_assets": 900_000,
    }
    data.update(overrides)
    snap = FinancialSnapshot(symbol="TEST", fiscal_period="1402")
    for k, v in data.items():
        setattr(snap, k, v)
    return snap


# ─────────────────────────── ISA 315: Risk Assessment ─────────────────


class TestAuditRiskAssessment:


    def test_assertion_risk_calculation(self):
        ar = AssertionRisk(
            assertion="occurrence",
            inherent_risk=0.6,
            control_risk=0.5,
            detection_risk=0.4,
        )
        ar.calculate_combined()
        assert ar.combined_risk == 0.6 * 0.5 * 0.4
        assert ar.combined_risk >= 0.05

    def test_account_risk_profile(self):
        profile = AccountRiskProfile(account_name="revenue", account_type="revenue")
        for a in ["occurrence", "completeness", "accuracy"]:
            ar = AssertionRisk(
                assertion=a, inherent_risk=0.5, control_risk=0.4, detection_risk=0.3
            )
            ar.calculate_combined()
            profile.assertion_risks[a] = ar
        profile.calculate_overall()
        assert profile.overall_risk_level in ("low", "medium", "high")
        assert isinstance(profile.key_assertions, list)


    def test_entity_level_risks(self):
        assessor = AuditRiskAssessor()
        snap = _make_snap()
        risks = assessor.assess_entity_level_risks(snap)
        assert isinstance(risks, dict)
        for key in [
            "management_override_of_controls",
            "fraud_in_revenue_recognition",
            "related_party_transactions",
            "going_concern_risk",
        ]:
            assert key in risks
            assert 0 <= risks[key] <= 1


    def test_account_risk_assessment(self):
        assessor = AuditRiskAssessor()
        snap = _make_snap()
        profiles = assessor.assess_account_risks(snap)
        assert "revenue" in profiles
        assert "receivables" in profiles
        assert "inventory" in profiles
        for _name, profile in profiles.items():
            assert profile.overall_risk_score >= 0
            assert profile.overall_risk_level in ("low", "medium", "high")


    def test_full_assessment(self):
        assessor = AuditRiskAssessor()
        snap = _make_snap()
        assessment = assessor.assess_all(snap)
        assert assessment.overall_audit_risk >= 0
        assert assessment.entity_level_risk_level in ("low", "medium", "high")
        assert "high_risk_accounts" in assessment.risk_summary
        assert "key_assertions_by_account" in assessment.risk_summary


    def test_format_response(self):
        assessor = AuditRiskAssessor()
        snap = _make_snap()
        assessment = assessor.assess_all(snap)
        response = format_risks_for_response(assessment)
        assert "entity_level_risks" in response
        assert "account_risk_profiles" in response
        assert "overall_audit_risk" in response


# ────────────────────────────── ISA 320: Materiality ──────────────────


class TestAuditMateriality:


    def test_calculate_levels(self):
        calc = MaterialityCalculator()
        snap = _make_snap()
        levels = calc.calculate_levels(snap)
        assert len(levels) > 0
        for lvl in levels:
            assert lvl.amount > 0
            assert lvl.benchmark_name in (
                "revenue",
                "total_assets",
                "net_profit",
                "total_equity",
            )

    def test_assess_all(self):
        calc = MaterialityCalculator()
        snap = _make_snap()
        mat = calc.assess_all(snap)
        assert mat.planning_materiality > 0
        assert mat.performance_materiality > 0
        assert mat.clearly_trivial_threshold > 0
        assert 0 < mat.performance_materiality <= mat.planning_materiality
        assert mat.clearly_trivial_threshold < mat.performance_materiality


    def test_revision(self):
        calc = MaterialityCalculator()
        snap = _make_snap(revenue=1_000_000)
        mat = calc.assess_all(snap)
        original_pm = mat.planning_materiality

        revised_snap = _make_snap(revenue=2_000_000)
        revised = calc.revise_materiality(
            mat, revised_snap, "Material change in revenue"
        )
        assert len(revised.revision_history) == 1
        assert revised.revision_history[0]["previous_pm"] == original_pm

        assert revised.revision_history[0]["reason"] == "Material change in revenue"



    def test_format_response(self):
        calc = MaterialityCalculator()
        snap = _make_snap()
        mat = calc.assess_all(snap)
        response = format_materiality_for_response(mat)
        assert "planning_materiality" in response
        assert "performance_materiality" in response
        assert "clearly_trivial_threshold" in response
        assert "levels" in response


# ────────────────────────── ISA 330: Control Testing ──────────────────


class TestControlTesting:


    def test_cycle_control_testing(self):
        tester = ControlTester()
        assessment = tester.test_cycle_controls("revenue_cycle")
        assert assessment.cycle_name == "revenue_cycle"
        assert len(assessment.control_tests) > 0
        for ct in assessment.control_tests:
            assert ct.sample_size > 0
            assert ct.result in ("effective", "partially_effective", "ineffective")

    def test_cycle_with_deviations(self):
        tester = ControlTester()
        devs = {"RC1": 3, "RC2": 1}
        assessment = tester.test_cycle_controls("revenue_cycle", devs)
        rc1_test = [ct for ct in assessment.control_tests if ct.control_code == "RC1"][
            0
        ]
        assert rc1_test.deviations_found == 3

    def test_all_cycles(self):
        tester = ControlTester()
        result = tester.assess_all_cycles()
        assert len(result.cycle_assessments) >= 5
        assert result.overall_effectiveness in (
            "effective",
            "effective_with_deficiencies",
            "partially_effective",
            "ineffective",
        )


    def test_audit_program_generation(self):
        gen = AuditProgramGenerator()
        program = gen.generate_program("revenue", "high")
        assert program.account == "revenue"
        assert len(program.procedures) > 0
        for proc in program.procedures:
            assert proc.assertion in (
                "occurrence",
                "completeness",
                "accuracy",
                "cutoff",
                "classification",
                "existence",
                "rights_obligations",
                "valuation",
            )

    def test_full_audit_program(self):
        gen = AuditProgramGenerator()
        programs = gen.generate_full_audit_program(
            ["revenue", "receivables"],
            {"revenue": "high", "receivables": "medium"},
        )
        assert "revenue" in programs
        assert "receivables" in programs

    def test_format_control_testing(self):
        tester = ControlTester()
        assessment = tester.assess_all_cycles()
        response = format_control_testing_for_response(assessment)
        assert "overall_effectiveness" in response
        assert "cycles" in response


    def test_format_audit_program(self):
        gen = AuditProgramGenerator()
        programs = gen.generate_full_audit_program(["revenue"])
        response = format_audit_program_for_response(programs)
        assert "revenue" in response


# ────────────────────────── ISA 450: Misstatement ─────────────────────


class TestMisstatementEvaluation:


    def test_record_misstatement(self):
        evaluator = MisstatementEvaluator()
        ms = evaluator.record_misstatement(
            "M1", "Error in revenue cutoff", 50_000, "factual", "revenue"
        )
        assert ms.reference == "M1"
        assert ms.amount == 50_000
        assert ms.category == "factual"

    def test_mark_corrected(self):
        evaluator = MisstatementEvaluator()
        evaluator.record_misstatement("M1", "Test", 10_000, "factual", "revenue")
        assert evaluator.mark_corrected("M1") is True
        assert evaluator.misstatements[0].is_corrected is True

    def test_evaluation_unmodified(self):
        evaluator = MisstatementEvaluator()
        evaluator.record_misstatement("M1", "Small error", 1_000, "factual", "revenue")
        evaluation = evaluator.evaluate(planning_materiality=100_000)
        assert evaluation.is_material is False
        assert evaluation.is_pervasive is False
        assert evaluation.proposed_opinion == "unmodified"


    def test_evaluation_qualified(self):
        evaluator = MisstatementEvaluator()
        evaluator.record_misstatement(
            "M1", "Material error", 90_000, "factual", "revenue"
        )
        evaluation = evaluator.evaluate(
            planning_materiality=100_000, performance_materiality=75_000
        )
        assert evaluation.is_material is True
        assert evaluation.is_pervasive is False
        assert evaluation.proposed_opinion == "qualified"


    def test_evaluation_adverse(self):
        evaluator = MisstatementEvaluator()
        evaluator.record_misstatement(
            "M1", "Pervasive error", 250_000, "factual", "revenue"
        )
        evaluation = evaluator.evaluate(
            planning_materiality=100_000, performance_materiality=75_000
        )
        assert evaluation.is_pervasive is True
        assert evaluation.proposed_opinion == "adverse"


    def test_project_misstatement(self):
        evaluator = MisstatementEvaluator()
        ms = evaluator.project_misstatement(
            sample_misstatement=5_000,
            population_value=1_000_000,
            sample_value=50_000,
            description="Projected inventory error",
            account="inventory",
        )
        assert ms.amount == 100_000  # 5000 * (1M / 50K)
        assert ms.category == "projected"


    def test_summary_counts(self):
        evaluator = MisstatementEvaluator()
        evaluator.record_misstatement("M1", "Factual", 10_000, "factual", "revenue")
        evaluator.record_misstatement(
            "M2", "Judgmental", 20_000, "judgmental", "receivables"
        )
        evaluator.record_misstatement(
            "M3", "Projected", 15_000, "projected", "inventory"
        )
        evaluation = evaluator.evaluate(planning_materiality=100_000)
        assert evaluation.summary.factual_count == 1
        assert evaluation.summary.judgmental_count == 1
        assert evaluation.summary.projected_count == 1
        assert evaluation.summary.total_uncorrected == 45_000


    def test_format_response(self):
        evaluator = MisstatementEvaluator()
        evaluator.record_misstatement("M1", "Test error", 5_000, "factual", "revenue")
        evaluation = evaluator.evaluate(planning_materiality=100_000)
        response = format_misstatements_for_response(evaluation)
        assert "summary" in response
        assert "misstatements" in response
        assert "proposed_opinion" in response


# ──────────────────────── Advanced Sampling ────────────────────────────


class TestAuditSampling:


    def test_stratified_sampling(self):
        sampler = StratifiedSampler(random_seed=42)
        items = [{"id": i + 1, "value": i + 1} for i in range(100)]
        result = sampler.sample_all(items)
        assert result.total_population_items == 100
        assert result.total_sample_size > 0
        assert len(result.strata) == 3

    def test_stratified_sampling_empty(self):
        sampler = StratifiedSampler()
        result = sampler.sample_all([])
        assert result.total_population_items == 0

    def test_attribute_sampling_sample_size(self):
        pass

        size = _attribute_sampling_sample_size(0.01, 0.05)
        assert size >= 25


    def test_attribute_sampling_evaluate(self):
        sampler = AttributeSampler()
        result = sampler.evaluate_results(100, 0, 0.05)
        assert result.is_acceptable is True
        assert result.sample_size == 100


    def test_attribute_sampling_reject(self):
        sampler = AttributeSampler()
        result = sampler.evaluate_results(50, 5, 0.03)
        assert result.is_acceptable is False


    def test_classical_variables_sampling(self):
        sampler = ClassicalVariablesSampler()
        book_values = [1000,
        2000,
        1500,
        3000,
        2500,
        1800,
        2200,
        1600,
        1900,
        2100]
        audited_values = [950,
        1950,
        1480,
        2900,
        2480,
        1750,
        2180,
        1550,
        1880,
        2050]
        result = sampler.evaluate_results(
            audited_values,
            book_values,
            population_size=100,
            population_value=200_000,
            tolerable_misstatement=20_000,
        )
        assert result.sample_size == len(book_values)
        assert result.precision > 0

    def test_pps_sampling(self):
        sampler = PPSampler(random_seed=42)
        items = [{"id": i + 1, "value": i + 1} for i in range(50)]
        selected = sampler.select_sample(items, materiality=100_000)
        assert len(selected) > 0
        assert len(selected) <= len(items)


    def test_format_sampling_stratified(self):
        sampler = StratifiedSampler(random_seed=42)
        items = [{"id": i + 1, "value": i + 1} for i in range(50)]
        result = sampler.sample_all(items)
        response = format_sampling_for_response(result)
        assert response["type"] == "stratified_sampling"


    def test_format_sampling_attribute(self):
        sampler = AttributeSampler()
        result = sampler.evaluate_results(100, 1, 0.05)
        response = format_sampling_for_response(result)
        assert response["type"] == "attribute_sampling"


    def test_all_sampling_types_present(self):
        assert hasattr(StratifiedSampler, "sample_all")
        assert hasattr(AttributeSampler, "evaluate_results")
        assert hasattr(ClassicalVariablesSampler, "evaluate_results")
        assert hasattr(PPSampler, "select_sample")


# ──────────────────────── ISA 240: Fraud Detection ──────────────────


class TestFraudDetection:


    def test_fraud_triangle(self):
        fa = FraudAssessor()
        snap = _make_snap(
            net_profit=-50_000, total_liabilities=2_000_000, total_equity=500_000
        )
        factors = fa.assess_fraud_triangle(snap)
        assert len(factors) > 0
        for f in factors:
            assert f.factor_type in (
                "incentive_pressure",
                "opportunity",
                "rationalization",
            )

    def test_revenue_fraud_indicators(self):
        fa = FraudAssessor()
        snap = _make_snap(operating_cash_flow=30_000, net_profit=200_000)
        indicators = fa.assess_revenue_fraud(snap)
        assert len(indicators) == len(REVENUE_FRAUD_INDICATORS)
        assert any(i.is_present for i in indicators)


    def test_asset_fraud_indicators(self):
        fa = FraudAssessor()
        snap = _make_snap()
        indicators = fa.assess_asset_fraud(snap)
        assert len(indicators) == len(ASSET_FRAUD_INDICATORS)


    def test_full_fraud_assessment(self):
        fa = FraudAssessor()
        snap = _make_snap(net_profit=-50_000)
        assessment = fa.assess_all(snap)
        assert assessment.overall_fraud_risk >= 0
        assert assessment.risk_level in ("low", "medium", "high")
        assert len(assessment.journal_entry_testing_approach) > 0


    def test_format_fraud_response(self):
        fa = FraudAssessor()
        snap = _make_snap()
        assessment = fa.assess_all(snap)
        response = format_fraud_for_response(assessment)
        assert "overall_fraud_risk" in response
        assert "revenue_indicators" in response
        assert "journal_entry_testing_approach" in response


# ──────────────────────── ISA 540: Estimates ────────────────────────


class TestEstimates:


    def test_range_testing(self):
        ea = EstimatesAuditor()
        result = ea.test_range(100_000, 80_000, 120_000)
        assert result.is_reasonable is True
        assert result.low == 80_000

    def test_range_outside(self):
        ea = EstimatesAuditor()
        result = ea.test_range(100_000, 50_000, 70_000)
        assert result.is_reasonable is False

    def test_warranty_provision(self):
        ea = EstimatesAuditor()
        result = ea.assess_warranty_provision(
            revenue=1_000_000,
            historical_claim_rate=0.02,
            avg_cost_per_claim=500,
            recorded_provision=8_000,
        )
        assert result.provision_type == "warranty"
        assert result.risk_level in ("low", "medium", "high")


    def test_doubtful_debts(self):
        ea = EstimatesAuditor()
        result = ea.assess_doubtful_debts(
            receivables=500_000,
            historical_default_rate=0.05,
            recorded_allowance=20_000,
        )
        assert result.provision_type == "doubtful_debts"


# ──────────────────────── ISA 550: Related Parties ──────────────────


class TestRelatedParties:


    def test_check_indicators(self):
        rpa = RelatedPartyAuditor()
        indicators = rpa.check_indicators(
            [
                "Significant transactions with non-routine counterparties",
            ]
        )
        assert len(indicators) == 1

    def test_assess_clean(self):
        rpa = RelatedPartyAuditor()
        assessment = rpa.assess([])
        assert assessment.overall_risk == "low"
        assert len(assessment.procedures_performed) > 0

    def test_assess_with_risk(self):
        rpa = RelatedPartyAuditor()
        txns = [
            {
                "counterparty": "RelatedCo",
                "relationship": "Subsidiary",
                "nature": "Consulting fees",
                "amount": 5_000_000_000,
                "terms": "favorable",
            },
        ]
        assessment = rpa.assess(txns)
        assert len(assessment.arm_slength_issues) > 0
        assert assessment.overall_risk == "high"


# ──────────────────────── ISA 560: Subsequent Events ────────────────


class TestSubsequentEvents:


    def test_classify_adjusting(self):
        event = SubsequentEventsAuditor.classify_event(
            "settlement of litigation after period end", 500_000
        )
        assert event.event_type == "adjusting"

    def test_classify_non_adjusting(self):
        event = SubsequentEventsAuditor.classify_event(
            "major business combination", 10_000_000
        )
        assert event.event_type == "non_adjusting"

    def test_assess_events(self):
        sa = SubsequentEventsAuditor()
        events = [
            {"description": "bankruptcy of customer", "amount": 500_000},
            {"description": "issue of shares after period end", "amount": 2_000_000},
        ]
        assessment = sa.assess(events)
        assert len(assessment.adjusting_events) == 1
        assert len(assessment.non_adjusting_events) == 1
        assert len(assessment.procedures_performed) > 0


# ──────────────────────── ISA 700/705: Opinion ──────────────────────


class TestOpinionFormulation:


    def test_unmodified(self):
        of = OpinionFormulator()
        opinion = of.form_opinion(
            uncorrected_misstatements=10_000,
            planning_materiality=100_000,
        )
        assert opinion.opinion_type == "unmodified"

    def test_qualified(self):
        of = OpinionFormulator()
        opinion = of.form_opinion(
            uncorrected_misstatements=90_000,
            planning_materiality=100_000,
        )
        assert opinion.opinion_type == "qualified"

    def test_adverse(self):
        of = OpinionFormulator()
        opinion = of.form_opinion(
            uncorrected_misstatements=250_000,
            planning_materiality=100_000,
        )
        assert opinion.opinion_type == "adverse"


    def test_disclaimer(self):
        of = OpinionFormulator()
        opinion = of.form_opinion(
            uncorrected_misstatements=0,
            planning_materiality=100_000,
            scope_limitations=[
                "Unable to observe inventory",
                "Unable to confirm receivables",
            ],
        )
        assert opinion.opinion_type in ("disclaimer", "qualified_disclaimer")


# ──────────────────────── ISA 230: Documentation ────────────────────


class TestDocumentation:


    def test_create_audit_file(self):
        af = AuditDocumenter.create_audit_file("TestCo", "1402")
        assert af.entity == "TestCo"
        assert af.period == "1402"
        assert len(af.sections) == 7

    def test_add_working_paper(self):
        af = AuditDocumenter.create_audit_file("TestCo", "1402")
        wp = AuditDocumenter.create_working_paper("C1", "Cash confirmation")
        AuditDocumenter.add_working_paper(
            af, "Substantive Procedures - Balance Sheet", wp
        )
        section_wps = af.sections["Substantive Procedures - Balance Sheet"]
        assert len(section_wps) == 1
        assert section_wps[0].wp_ref == "C1"

    def test_completeness_check(self):
        af = AuditDocumenter.create_audit_file("TestCo", "1402")
        assert af.file_complete is False
        AuditDocumenter.check_completeness(af)
        assert af.file_complete is True


    def test_format_response(self):
        af = AuditDocumenter.create_audit_file("TestCo", "1402")
        response = format_documentation_for_response(af)
        assert "section_summary" in response
        assert "wp_index" in response


# ──────────────────────── ISA 300: Audit Planning ───────────────────


class TestAuditPlanning:


    def test_create_strategy(self):
        ap = AuditPlanner()
        strategy = ap.create_strategy("TestCo", "1402")
        assert strategy.entity == "TestCo"
        assert len(strategy.team) == 4
        assert len(strategy.timeline) == 4

    def test_preliminary_analytics(self):
        ap = AuditPlanner()
        results = ap.preliminary_analytical_procedures(
            {"revenue": 1_200_000, "net_profit": 200_000},
            {"revenue": 1_000_000, "net_profit": 150_000},
        )
        assert len(results) == 2
        rev_result = next(r for r in results if r.procedure.startswith("revenue"))
        assert rev_result.variance_pct == 20.0

    def test_assess_scope(self):
        ap = AuditPlanner()
        scope = ap.assess_scope(
            [
                {"name": "Tehran HQ", "revenue_pct": 60},
                {"name": "Mashhad Branch", "revenue_pct": 10},
            ]
        )
        assert scope["significant_locations"] == 1


# ──────────────────────── ISA 500: Audit Evidence ────────────────────


class TestAuditEvidence:


    def test_reliability_scores(self):
        assert EvidenceEvaluator.reliability("external_confirmation") == 0.95
        assert EvidenceEvaluator.reliability("inquiry") == 0.30

    def test_assess_evidence(self):
        ec = EvidenceEvaluator.assess_evidence(
            "revenue", ["occurrence", "accuracy", "cutoff"]
        )
        assert ec.account == "revenue"
        assert len(ec.items) > 0
        for item in ec.items:
            assert item.assertion in ("occurrence", "accuracy", "cutoff")

    def test_evidence_gaps(self):
        ec = EvidenceEvaluator.assess_evidence(
            "inventory", ["existence", "valuation"]
        )
        assert ec.overall_sufficiency in ("adequate", "inadequate")

    def test_format_response(self):
        ec = EvidenceEvaluator.assess_evidence(
            "receivables", ["existence", "valuation"]
        )
        response = format_evidence_for_response(ec)
        assert "overall_sufficiency" in response
        assert "evidence_items" in response


# ──────────────────────── ISA 505: Confirmations ─────────────────────


class TestConfirmations:


    def test_create_request(self):
        cr = ConfirmationManager.create_request("CustomerA", "receivables", 500_000)
        assert cr.entity_name == "CustomerA"
        assert cr.balance == 500_000
        assert cr.status == "pending"

    def test_record_response_confirmed(self):
        cr = ConfirmationManager.create_request("CustomerA", "receivables", 100_000)
        ConfirmationManager.record_response(cr, 100_000)
        assert cr.status == "confirmed"
        assert cr.difference == 0

    def test_record_response_exception(self):
        cr = ConfirmationManager.create_request("CustomerA", "receivables", 100_000)
        ConfirmationManager.record_response(cr, 90_000, "Difference found")
        assert cr.status == "exception"
        assert cr.difference == 10_000

    def test_summary(self):
        reqs = [
            ConfirmationManager.create_request("A", "AR", 100_000),
            ConfirmationManager.create_request("B", "AR", 200_000),
        ]
        ConfirmationManager.record_response(reqs[0], 100_000)
        summary = ConfirmationManager.summarize(reqs, 300_000)
        assert summary.total_sent == 2
        assert summary.confirmed_without_exception == 1
        assert summary.responses_received == 1


    def test_format_response(self):
        reqs = [ConfirmationManager.create_request("A", "AR", 100_000)]
        ConfirmationManager.record_response(reqs[0], 100_000)
        summary = ConfirmationManager.summarize(reqs)
        response = format_confirmation_for_response(summary, reqs)
        assert "summary" in response
        assert "requests" in response


# ──────────────────────── ISA 580: Representations ───────────────────


class TestRepresentations:


    def test_create_letter(self):
        letter = RepresentationManager.create_letter("TestCo", "1402")
        assert letter.entity == "TestCo"
        assert len(letter.items) == 14

    def test_obtain_single(self):
        letter = RepresentationManager.create_letter("TestCo", "1402")
        RepresentationManager.obtain_representation(letter, 0, "1402/12/29")
        assert letter.items[0].is_obtained is True
        assert letter.items[0].date_obtained == "1402/12/29"

    def test_obtain_all(self):
        letter = RepresentationManager.create_letter("TestCo", "1402")
        RepresentationManager.obtain_all(letter, "1402/12/29")
        RepresentationManager.check_completeness(letter)
        assert letter.all_obtained is True
        assert letter.missing_count == 0

    def test_missing(self):
        letter = RepresentationManager.create_letter("TestCo", "1402")
        RepresentationManager.check_completeness(letter)
        assert letter.all_obtained is False
        assert letter.missing_count == 14


    def test_format_response(self):
        letter = RepresentationManager.create_letter("TestCo", "1402")
        RepresentationManager.obtain_all(letter, "1402/12/29")
        RepresentationManager.check_completeness(letter)
        response = format_representation_for_response(letter)
        assert "all_obtained" in response
        assert "items" in response


# ──────────────────────── ISA 501: Specific Evidence ─────────────────


class TestSpecificEvidence:


    def test_inventory_observation_satisfactory(self):
        result = SpecificEvidenceAssessor.inventory_observation(
            "Warehouse A", "1402/12/29", 100, 1
        )
        assert result.accuracy_assessment == "satisfactory"
        assert result.difference_rate == 0.01

    def test_inventory_observation_unsatisfactory(self):
        result = SpecificEvidenceAssessor.inventory_observation(
            "Warehouse A", "1402/12/29", 100, 10
        )
        assert result.accuracy_assessment == "unsatisfactory"

    def test_litigation_probable(self):
        result = SpecificEvidenceAssessor.litigation_assessment(
            "Case1", "Tax dispute", 1_000_000, "probable"
        )
        assert result.provision_required is True
        assert result.recommended_provision == 800_000


    def test_litigation_remote(self):
        result = SpecificEvidenceAssessor.litigation_assessment(
            "Case1", "Minor claim", 10_000, "remote"
        )
        assert result.provision_required is False
        assert result.disclosure_required is False


    def test_opening_balances_first_engagement(self):
        result = SpecificEvidenceAssessor.opening_balances(prior_audited=False)
        assert result.adjustment_required is True
        assert "first audit" in result.conclusion.lower()


    def test_opening_balances_clean(self):
        result = SpecificEvidenceAssessor.opening_balances(
            prior_audited=True, prior_opinion="unmodified"
        )
        assert result.adjustment_required is False
        assert "consistent" in result.conclusion.lower()


    def test_format_specific_evidence(self):
        result = SpecificEvidenceAssessor.inventory_observation(
            "WH1", "1402/12/29", 100, 1
        )
        response = format_specific_evidence_for_response(result)
        assert response["type"] == "inventory_observation"


# ──────────────────────── ISA 220: Quality Control ───────────────────


class TestQualityControl:


    def test_independence_clean(self):
        ic = QualityControlManager.check_independence()
        assert ic.is_independent is True
        assert "confirmed" in ic.conclusion

    def test_independence_impaired(self):
        ic = QualityControlManager.check_independence(has_financial_interest=True)
        assert ic.is_independent is False

    def test_eqcr_clean(self):
        review = QualityControlManager.eqc_review(
            "Partner A", "Reviewer B", "1402/12/29"
        )
        assert review.all_resolved is True
        assert "completed" in review.overall_conclusion

    def test_eqcr_with_findings(self):
        review = QualityControlManager.eqc_review(
            "Partner A",
            "Reviewer B",
            "1402/12/29",
            [
                {
                    "area": "Revenue",
                    "finding": "Cutoff testing incomplete",
                    "severity": "high",
                    "is_resolved": False,
                },
            ],
        )
        assert review.all_resolved is False


    def test_format_qc(self):
        ic = QualityControlManager.check_independence()
        response = format_qc_for_response(ic)
        assert response["type"] == "independence_check"


# ──────────────────────── ISA 260: Governance Communication ──────────


class TestGovernanceCommunication:


    def test_create_plan(self):
        plan = GovernanceCommunicator.create_plan("TestCo", "1402")
        assert plan.entity == "TestCo"
        assert len(plan.committee_meetings) == 4
        assert len(plan.communication_items) == 15

    def test_mark_communicated(self):
        plan = GovernanceCommunicator.create_plan("TestCo", "1402")
        GovernanceCommunicator.mark_communicated(plan, "Significant risks identified")
        GovernanceCommunicator.check_completeness(plan)
        assert len(plan.pending_items) == 14

    def test_all_communicated(self):
        plan = GovernanceCommunicator.create_plan("TestCo", "1402")
        for item in plan.communication_items:
            GovernanceCommunicator.mark_communicated(plan, item)
        GovernanceCommunicator.check_completeness(plan)
        assert plan.all_communicated is True


    def test_add_record(self):
        plan = GovernanceCommunicator.create_plan("TestCo", "1402")
        GovernanceCommunicator.add_record(
            plan,
            "Planning",
            "1402/10/01",
            "Audit Committee",
            "meeting",
            "Scope discussed",
        )
        assert len(plan.records) == 1


    def test_format_response(self):
        plan = GovernanceCommunicator.create_plan("TestCo", "1402")
        response = format_governance_for_response(plan)
        assert "communication_status" in response
        assert "committee_meetings" in response
