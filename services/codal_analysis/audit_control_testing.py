from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

CONTROL_CYCLES = {
    "revenue_cycle": {
        "title": "چرخه فروش",
        "controls": [
            {"code": "RC1", "description": "اعتبار مشتری قبل از ثبت سفارش بررسی می‌شود", "control_type": "preventive", "frequency": "daily"},
            {"code": "RC2", "description": "سفارشات با قیمت‌نامه مصوب تطبیق داده می‌شود", "control_type": "preventive", "frequency": "daily"},
            {"code": "RC3", "description": "فاکتورها با اسناد حمل تطبیق داده می‌شود", "control_type": "detective", "frequency": "daily"},
            {"code": "RC4", "description": "حذف یا تعدیل فاکتور نیاز به تأیید مدیریت دارد", "control_type": "preventive", "frequency": "weekly"},
            {"code": "RC5", "description": "صورت‌های حساب مشتریان به صورت دوره‌ای ارسال می‌شود", "control_type": "detective", "frequency": "monthly"},
        ],
    },
    "procurement_cycle": {
        "title": "چرخه خرید و پرداخت",
        "controls": [
            {"code": "PC1", "description": "خرید بالای سقف نیاز به سه پیش فاکتور دارد", "control_type": "preventive", "frequency": "daily"},
            {"code": "PC2", "description": "کالاهای خریداری شده با سفارش خرید تطبیق داده می‌شود", "control_type": "detective", "frequency": "daily"},
            {"code": "PC3", "description": "فاکتور تأمین‌کننده قبل از پرداخت تأیید می‌شود", "control_type": "preventive", "frequency": "daily"},
            {"code": "PC4", "description": "دسته‌های چک بانک به امضای مشترک می‌رسد", "control_type": "preventive", "frequency": "weekly"},
            {"code": "PC5", "description": "ثبت خرید و پرداخت به صورت ماهانه بایگانی می‌شود", "control_type": "detective", "frequency": "monthly"},
        ],
    },
    "payroll_cycle": {
        "title": "چرخه حقوق و دستمزد",
        "controls": [
            {"code": "PR1", "description": "لیست حقوق با حضور و غیاب تطبیق داده می‌شود", "control_type": "detective", "frequency": "monthly"},
            {"code": "PR2", "description": "اضافه‌کار با تأیید سرپرست ثبت می‌شود", "control_type": "preventive", "frequency": "daily"},
            {"code": "PR3", "description": "کسر و اضافات حقوق با مدارک پشتیبان ثبت می‌شود", "control_type": "preventive", "frequency": "monthly"},
            {"code": "PR4", "description": "ورم‌های حقوق ماهانه توسط مدیر مالی تأیید می‌شود", "control_type": "preventive", "frequency": "monthly"},
        ],
    },
    "treasury_cycle": {
        "title": "چرخه خزانه‌داری",
        "controls": [
            {"code": "TC1", "description": "انتقال وجه بین حساب‌ها نیاز به تأیید دو نفره دارد", "control_type": "preventive", "frequency": "daily"},
            {"code": "TC2", "description": "صورت‌های بانکی به صورت ماهانه تطبیق داده می‌شود", "control_type": "detective", "frequency": "monthly"},
            {"code": "TC3", "description": "تنخواه گردان‌ها به صورت دوره‌ای تسویه می‌شود", "control_type": "detective", "frequency": "monthly"},
            {"code": "TC4", "description": "سرمایه‌گذاری‌های کوتاه مدت با مصوبه هیئت مدیره انجام می‌شود", "control_type": "preventive", "frequency": "daily"},
        ],
    },
    "financial_reporting": {
        "title": "چرخه گزارشگری مالی",
        "controls": [
            {"code": "FR1", "description": "تراز آزمایشی قبل از تهیه صورت‌های مالی بسته می‌شود", "control_type": "detective", "frequency": "monthly"},
            {"code": "FR2", "description": "ثبت‌های اصلاحی با مستندات پشتیبان تهیه می‌شود", "control_type": "preventive", "frequency": "monthly"},
            {"code": "FR3", "description": "صورت‌های مالی قبل از انتشار توسط حسابرس داخلی بررسی می‌شود", "control_type": "detective", "frequency": "quarterly"},
            {"code": "FR4", "description": "تغییرات در رویه‌های حسابداری مستند و افشا می‌شود", "control_type": "detective", "frequency": "annual"},
        ],
    },
}


@dataclass
class ControlTestResult:
    control_code: str
    control_description: str
    control_type: str
    frequency: str
    sample_size: int
    deviations_found: int
    deviation_rate: float
    tolerable_rate: float
    test_procedure: str = ""
    result: str = "not_tested"
    conclusion: str = ""
    severity: str = "none"


@dataclass
class ControlCycleAssessment:
    cycle_name: str
    cycle_title: str
    control_tests: list[ControlTestResult] = field(default_factory=list)
    cycle_effectiveness: str = "untested"
    deficiencies_count: int = 0
    significant_deficiencies: int = 0
    material_weaknesses: int = 0


@dataclass
class OverallControlAssessment:
    cycle_assessments: dict[str, ControlCycleAssessment] = field(default_factory=dict)
    overall_effectiveness: str = "untested"
    material_weakness_exists: bool = False
    significant_deficiencies: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AuditProgramProcedure:
    procedure_code: str
    procedure_description: str
    account: str
    assertion: str
    procedure_type: str
    sample_size: int | None = None
    evidence_required: str = ""


@dataclass
class AuditProgram:
    program_name: str = ""
    account: str = ""
    procedures: list[AuditProgramProcedure] = field(default_factory=list)
    total_procedures: int = 0


ACCOUNT_AUDIT_PROGRAMS: dict[str, list[dict[str, Any]]] = {
    "revenue": [
        {"code": "REV01", "desc": "مقایسه درآمد ثبت شده با بودجه و دوره قبل", "assertion": "accuracy", "type": "substantive_analytical"},
        {"code": "REV02", "desc": "بررسی نمونه فاکتورهای فروش برای تطبیق با اسناد حمل", "assertion": "occurrence", "type": "test_of_details"},
        {"code": "REV03", "desc": "بررسی ثبت فروش نزدیک تاریخ ترازنامه (cutoff testing)", "assertion": "cutoff", "type": "test_of_details"},
        {"code": "REV04", "desc": "بررسی برگشت از فروش و تخفیفات", "assertion": "accuracy", "type": "test_of_details"},
        {"code": "REV05", "desc": "تجزیه و تحلیل نسبت فروش به هزینه و حاشیه سود", "assertion": "completeness", "type": "substantive_analytical"},
    ],
    "receivables": [
        {"code": "AR01", "desc": "ارسال صورت حساب به نمونه مشتریان (circularization)", "assertion": "existence", "type": "test_of_details"},
        {"code": "AR02", "desc": "بررسی سن مطالبات و ذخیره مطالبات مشکوک الوصول", "assertion": "valuation", "type": "test_of_details"},
        {"code": "AR03", "desc": "بررسی وصول وجه پس از تاریخ ترازنامه", "assertion": "valuation", "type": "test_of_details"},
        {"code": "AR04", "desc": "تطبیق دفتر معین حساب‌های دریافتنی با کل", "assertion": "completeness", "type": "substantive_analytical"},
    ],
    "inventory": [
        {"code": "INV01", "desc": "حضور در شمارش فیزیکی موجودی کالا", "assertion": "existence", "type": "test_of_details"},
        {"code": "INV02", "desc": "بررسی اقلام کُنام (slow-moving) و تاریخ مصرف", "assertion": "valuation", "type": "test_of_details"},
        {"code": "INV03", "desc": "بررسی مبنای قیمت‌گذاری و محاسبه قیمت تمام شده", "assertion": "accuracy", "type": "test_of_details"},
        {"code": "INV04", "desc": "تطبیق شمارش فیزیکی با دفاتر", "assertion": "completeness", "type": "substantive_analytical"},
    ],
    "property_plant_equipment": [
        {"code": "PPE01", "desc": "بررسی افزایش دارایی‌های ثابت و استعلام اسناد مالکیت", "assertion": "existence", "type": "test_of_details"},
        {"code": "PPE02", "desc": "بررسی عمر مفید و روش استهلاک", "assertion": "valuation", "type": "substantive_analytical"},
        {"code": "PPE03", "desc": "بررسی واگذاری و کنارگذاری دارایی‌ها", "assertion": "completeness", "type": "test_of_details"},
        {"code": "PPE04", "desc": "بررسی استهلاک انباشته", "assertion": "accuracy", "type": "substantive_analytical"},
    ],
    "payables": [
        {"code": "AP01", "desc": "بررسی ثبت خرید نزدیک تاریخ ترازنامه (cutoff)", "assertion": "cutoff", "type": "test_of_details"},
        {"code": "AP02", "desc": "بررسی اسناد پرداختنی و تطبیق با صورتحساب", "assertion": "completeness", "type": "test_of_details"},
        {"code": "AP03", "desc": "استعلام از تأمین‌کنندگان", "assertion": "existence", "type": "test_of_details"},
        {"code": "AP04", "desc": "بررسی هزینه‌های تعهدی و ذخایر", "assertion": "completeness", "type": "substantive_analytical"},
    ],
    "cash_and_equivalents": [
        {"code": "CSH01", "desc": "تطبیق صورت حساب بانکی", "assertion": "existence", "type": "substantive_analytical"},
        {"code": "CSH02", "desc": "بررسی انتقال‌های بانکی نزدیک ترازنامه", "assertion": "cutoff", "type": "test_of_details"},
        {"code": "CSH03", "desc": "شمارش وجوه نقد", "assertion": "existence", "type": "test_of_details"},
        {"code": "CSH04", "desc": "بررسی محدودیت‌های وجوه نقد", "assertion": "rights_obligations", "type": "test_of_details"},
    ],
    "equity": [
        {"code": "EQ01", "desc": "بررسی تغییرات در حقوق صاحبان سهام", "assertion": "completeness", "type": "substantive_analytical"},
        {"code": "EQ02", "desc": "بررسی مصوبات مجمع در خصوص سود و سرمایه", "assertion": "occurrence", "type": "test_of_details"},
        {"code": "EQ03", "desc": "بررسی ذخایر قانونی و اختیاری", "assertion": "accuracy", "type": "test_of_details"},
    ],
}


def _attribute_sampling_sample_size(
    expected_deviation_rate: float,
    tolerable_rate: float,
    risk_of_overreliance: float = 0.05,
) -> int:
    if tolerable_rate <= expected_deviation_rate:
        return 0
    if expected_deviation_rate <= 0:
        return 25
    z = {0.10: 1.282, 0.05: 1.645, 0.01: 2.326}.get(risk_of_overreliance, 1.645)
    numerator = z ** 2 * (1 - expected_deviation_rate)
    denominator = (tolerable_rate - expected_deviation_rate) ** 2
    if denominator <= 0:
        return 100
    return max(25, min(200, int(numerator / denominator)))


class ControlTester:
    """ISA 330: The Auditor's Responses to Assessed Risks - Test of Controls"""

    def __init__(self, risk_of_overreliance: float = 0.05):
        self.risk_of_overreliance = risk_of_overreliance

    def test_cycle_controls(
        self,
        cycle_name: str,
        deviations: dict[str, int] | None = None,
    ) -> ControlCycleAssessment:
        cycle_config = CONTROL_CYCLES.get(cycle_name)
        if not cycle_config:
            return ControlCycleAssessment(cycle_name=cycle_name, cycle_title=cycle_name)

        deviations = deviations or {}
        assessment = ControlCycleAssessment(
            cycle_name=cycle_name,
            cycle_title=cycle_config["title"],
        )

        for ctrl in cycle_config["controls"]:
            code = ctrl["code"]
            deviation_count = deviations.get(code, 0)

            tolerable_rate = 0.03 if ctrl["control_type"] == "preventive" else 0.05
            expected_rate = 0.01

            sample_size = _attribute_sampling_sample_size(
                expected_rate, tolerable_rate, self.risk_of_overreliance
            )
            deviation_rate = deviation_count / sample_size if sample_size > 0 else 0

            if deviation_rate <= expected_rate:
                result = "effective"
                severity = "none"
                conclusion = "Control operating effectively"
            elif deviation_rate <= tolerable_rate:
                result = "partially_effective"
                severity = "deficiency"
                conclusion = "Deviations found but within tolerable rate"
            else:
                result = "ineffective"
                severity = "significant_deficiency" if deviation_rate > tolerable_rate * 1.5 else "deficiency"
                conclusion = "Control not operating effectively"

            test = ControlTestResult(
                control_code=code,
                control_description=ctrl["description"],
                control_type=ctrl["control_type"],
                frequency=ctrl["frequency"],
                sample_size=sample_size,
                deviations_found=deviation_count,
                deviation_rate=round(deviation_rate, 4),
                tolerable_rate=tolerable_rate,
                test_procedure=f"Select {sample_size} items and test for deviations",
                result=result,
                conclusion=conclusion,
                severity=severity,
            )
            assessment.control_tests.append(test)

            if severity == "significant_deficiency":
                assessment.significant_deficiencies += 1
            elif severity == "deficiency":
                assessment.deficiencies_count += 1
                if deviation_rate > tolerable_rate:
                    assessment.material_weaknesses += 1

        if assessment.material_weaknesses > 0:
            assessment.cycle_effectiveness = "ineffective"
        elif assessment.significant_deficiencies > 0:
            assessment.cycle_effectiveness = "partially_effective"
        elif assessment.deficiencies_count > 0:
            assessment.cycle_effectiveness = "effective_with_deficiencies"
        else:
            assessment.cycle_effectiveness = "effective"

        return assessment

    def assess_all_cycles(
        self,
        cycle_deviations: dict[str, dict[str, int]] | None = None,
    ) -> OverallControlAssessment:
        cycle_deviations = cycle_deviations or {}
        result = OverallControlAssessment()

        for cycle_name in CONTROL_CYCLES:
            deviations = cycle_deviations.get(cycle_name, {})
            cycle_assessment = self.test_cycle_controls(cycle_name, deviations)
            result.cycle_assessments[cycle_name] = cycle_assessment

        total_cycles = len(result.cycle_assessments)
        ineffective_count = sum(
            1 for c in result.cycle_assessments.values()
            if c.cycle_effectiveness == "ineffective"
        )
        partial_count = sum(
            1 for c in result.cycle_assessments.values()
            if c.cycle_effectiveness == "partially_effective"
        )

        if ineffective_count > 0:
            result.overall_effectiveness = "ineffective"
            result.material_weakness_exists = True
        elif partial_count > total_cycles * 0.5:
            result.overall_effectiveness = "partially_effective"
        elif partial_count > 0:
            result.overall_effectiveness = "effective_with_deficiencies"
        else:
            result.overall_effectiveness = "effective"

        for _name, ca in result.cycle_assessments.items():
            for ct in ca.control_tests:
                if ct.severity == "significant_deficiency":
                    result.significant_deficiencies.append(
                        f"{ca.cycle_title}: {ct.control_description}"
                    )

        result.recommendations = self._generate_recommendations(result)
        return result

    def _generate_recommendations(self, assessment: OverallControlAssessment) -> list[str]:
        recs = []
        for _name, ca in assessment.cycle_assessments.items():
            if ca.cycle_effectiveness in ("ineffective", "partially_effective"):
                recs.append(
                    f"تعمیر و بهبود کنترل‌های {ca.cycle_title}: "
                    f"{ca.significant_deficiencies} نقص بااهمیت و "
                    f"{ca.material_weaknesses} ضعف بااهمیت شناسایی شد"
                )
            for ct in ca.control_tests:
                if ct.severity == "significant_deficiency":
                    recs.append(
                        f"کنترل {ct.control_code} ({ct.control_description}): "
                        f"{ct.deviations_found} انحراف در {ct.sample_size} نمونه "
                        f"(نرخ انحراف: {ct.deviation_rate:.1%})"
                    )
        return recs


class AuditProgramGenerator:
    """Generates audit programs per account based on identified risks"""

    def __init__(self):
        self.programs: dict[str, AuditProgram] = {}

    def generate_program(
        self,
        account: str,
        risk_level: str = "medium",
        specific_focus: list[str] | None = None,
    ) -> AuditProgram:
        procedures_config = ACCOUNT_AUDIT_PROGRAMS.get(account, [])
        if not procedures_config:
            return AuditProgram(program_name=f"Program for {account}", account=account)

        program = AuditProgram(
            program_name=f"برنامه حسابرسی {account}",
            account=account,
        )

        specific_focus = specific_focus or []

        for cfg in procedures_config:

            if specific_focus and cfg["assertion"] not in specific_focus:
                continue

            if risk_level == "low" and cfg["type"] == "test_of_details":
                sample_multiplier = 0.5
            elif risk_level == "high":
                sample_multiplier = 1.5
            else:
                sample_multiplier = 1.0

            sample_size = None
            if cfg["type"] == "test_of_details":
                base_size = 25
                sample_size = max(10, int(base_size * sample_multiplier))

            proc = AuditProgramProcedure(
                procedure_code=cfg["code"],
                procedure_description=cfg["desc"],
                account=account,
                assertion=cfg["assertion"],
                procedure_type=cfg["type"],
                sample_size=sample_size,
                evidence_required="documentation" if cfg["type"] == "test_of_details" else "analysis",
            )
            program.procedures.append(proc)

        program.total_procedures = len(program.procedures)
        self.programs[account] = program
        return program

    def generate_full_audit_program(
        self,
        accounts: list[str],
        risk_levels: dict[str, str] | None = None,
        specific_focus: dict[str, list[str]] | None = None,
    ) -> dict[str, AuditProgram]:
        risk_levels = risk_levels or {}
        specific_focus = specific_focus or {}
        programs = {}
        for account in accounts:
            rl = risk_levels.get(account, "medium")
            sf = specific_focus.get(account, [])
            programs[account] = self.generate_program(account, rl, sf)
        return programs


def format_control_testing_for_response(assessment: OverallControlAssessment) -> dict[str, Any]:
    return {
        "overall_effectiveness": assessment.overall_effectiveness,
        "material_weakness_exists": assessment.material_weakness_exists,
        "significant_deficiencies": assessment.significant_deficiencies,
        "recommendations": assessment.recommendations,
        "cycles": {
            name: {
                "cycle_title": ca.cycle_title,
                "cycle_effectiveness": ca.cycle_effectiveness,
                "deficiencies_count": ca.deficiencies_count,
                "significant_deficiencies": ca.significant_deficiencies,
                "material_weaknesses": ca.material_weaknesses,
                "control_tests": [
                    {
                        "control_code": ct.control_code,
                        "description": ct.control_description,
                        "type": ct.control_type,
                        "frequency": ct.frequency,
                        "sample_size": ct.sample_size,
                        "deviations_found": ct.deviations_found,
                        "deviation_rate": ct.deviation_rate,
                        "tolerable_rate": ct.tolerable_rate,
                        "result": ct.result,
                        "severity": ct.severity,
                        "conclusion": ct.conclusion,
                    }
                    for ct in ca.control_tests
                ],
            }
            for name, ca in assessment.cycle_assessments.items()
        },
    }


def format_audit_program_for_response(programs: dict[str, AuditProgram]) -> dict[str, Any]:
    return {
        name: {
            "program_name": p.program_name,
            "account": p.account,
            "total_procedures": p.total_procedures,
            "procedures": [
                {
                    "procedure_code": pr.procedure_code,
                    "description": pr.procedure_description,
                    "assertion": pr.assertion,
                    "type": pr.procedure_type,
                    "sample_size": pr.sample_size,
                    "evidence_required": pr.evidence_required,
                }
                for pr in p.procedures
            ],
        }
        for name, p in programs.items()
    }
