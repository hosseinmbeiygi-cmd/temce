"""🧬 Registry contract: composition must be inertial for equity and honest elsewhere.

The instrument axis is only safe if adding it changed nothing for the 115 questions that
are already stored in users' sheets — so the identity is asserted, not assumed. The
synthetic module below is the only way to prove re-sequencing and ``replaces`` work
before a second real instrument class exists.
"""

from __future__ import annotations

import pytest

from core.question_bank import bank, registry
from core.question_bank.registry import (
    EQUITY,
    EvidenceContractError,
    InstrumentModule,
    UnknownInstrument,
    resolve,
)
from services.pre_buy_evidence import (
    _RESOLVERS,  # noqa: PLC2701 - the two together are the bind-or-declare contract
    PERMANENTLY_UNAVAILABLE,
)

_S = bank.stages()
_Q = bank.questions()


def test_equity_composition_is_the_identity() -> None:
    rb = resolve("equity")

    assert [(s.id, s.key, s.title) for s in rb.stages()] == [(s.id, s.key, s.title) for s in _S]
    assert [(q.code, q.stage, q.text) for q in rb.questions()] == [(q.code, q.stage, q.text) for q in _Q]
    assert rb.stopper_codes == bank.STOPPER_CODES
    assert rb.golden_codes == bank.GOLDEN_CODES
    assert rb.roles == bank.ROLLED_ROLES
    assert set(rb.evidence_by_key()) == set(bank.evidence_by_key())
    assert rb.instrument_type == "equity" and rb.label == "سهام"


def test_core_and_module_split_is_what_the_framework_says() -> None:
    """Stage 0 and stages 8-10 are shared; 1-7 are the stock-specific middle."""

    assert frozenset({0, 8, 9, 10}) == registry.CORE_STAGE_IDS
    assert {s.id for s in EQUITY.stages} == set(range(1, 8))
    core_only = [q for q in _Q if q.stage in registry.CORE_STAGE_IDS]
    assert len(core_only) == 36  # 11 + 8 + 7 + 10
    assert len(EQUITY.questions) == 79


def test_unauthored_class_raises_instead_of_reusing_stock_questions() -> None:
    """REIT is the document's class D and has no bank: no table holds a property fund.

    It must raise rather than inherit the stock or the fund questions, because the framework
    reserves ★ rejections for class-specific conditions.
    """

    with pytest.raises(UnknownInstrument) as exc:
        resolve("reit")
    assert exc.value.key == "reit"


def test_stage_numbers_are_re_sequenced_and_core_questions_can_be_tightened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.question_bank.schema import Question, Stage

    money = Question(code="PB-006", stage=0, text="سقف وزن هر سهم؟", kind="number")
    per_unit = Question(code="PB-006", stage=0, text="سقف وزن هر واحد؟", kind="number")
    module = InstrumentModule(
        key="fund",
        label="صندوق",
        stages=(Stage(0, "what", "ساختار صندوق", ""), Stage(1, "liq", "نقدشوندگی", "")),
        questions=(
            Question(code="PF-001", stage=0, text="نوع صندوق؟", kind="choice"),
            Question(code="PF-002", stage=1, text="صف؟", kind="yes_no_unknown"),
        ),
        # A module must claim the core handles too: the shared questions ask for them, and
        # a class that cannot source them is not allowed to inherit them silently.
        evidence=bank.evidence_by_key(),
        replaces={money.code: per_unit},
    )
    monkeypatch.setitem(registry.MODULES, "fund", module)

    rb = resolve("fund")

    assert [s.key for s in rb.stages()] == ["self", "what", "liq", "sizing", "exit", "mirror"]
    assert [s.id for s in rb.stages()] == list(range(6)), "ids are contiguous in play order"
    assert rb.question("PB-006").text == "سقف وزن هر واحد؟"
    # every question sits in the stage it was placed in, not its authoring number
    assert {q.code: q.stage for q in rb.questions()}["PF-002"] == 2
    assert rb.questions_by_stage(0)[0].code == "PB-001"
    assert set(rb.evidence_by_key()) == set(bank.evidence_by_key())


def test_question_referencing_an_unbound_handle_fails_the_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.question_bank.schema import Evidence, Question, Stage

    module = InstrumentModule(
        key="etf",
        label="صندوق قابل‌معامله",
        stages=(Stage(0, "prem", "پریمیوم", ""),),
        questions=(
            Question(
                code="PE-001",
                stage=0,
                text="پریمیوم چقدر است؟",
                kind="number",
                evidence=(Evidence("nav.premium", "پریمیوم", "GET /funds/{symbol}/nav"),),
            ),
        ),
    )
    monkeypatch.setitem(registry.MODULES, "etf", module)

    with pytest.raises(EvidenceContractError, match="nav.premium"):
        resolve("etf")


def test_every_authored_bank_binds_or_declares_each_handle() -> None:
    """Bind-or-declare, for every resolved bank rather than only the stock one.

    An evidence handle has two honest states: the resolver can read it from a real column, or
    the platform says out loud that it cannot. A third state — a handle with no binding and no
    declaration — would render as an empty «—» forever and read as "no data exists" rather than
    "this app never looked". That is the gap this test closes for every module, so adding an
    instrument class cannot reintroduce it.
    """

    for key in registry.MODULES:
        rb = resolve(key)
        catalogue = rb.evidence_by_key()
        used = {e.key for q in rb.questions() for e in q.evidence}

        assert used <= set(catalogue), f"{key}: handles no module declares {used - set(catalogue)}"
        unbound = {h for h in catalogue if h not in _RESOLVERS and h not in PERMANENTLY_UNAVAILABLE}
        assert not unbound, f"{key}: neither bound nor declared: {sorted(unbound)}"
        for handle, reason in PERMANENTLY_UNAVAILABLE.items():
            if handle in catalogue:
                assert reason.strip(), f"{key}: {handle} is declared unavailable without a reason"


def test_a_permanently_unavailable_handle_is_still_a_declared_one() -> None:
    """Declaring a gap is not a licence to invent one: it must name a handle questions use."""

    declared_here = set(bank.evidence_by_key())
    for key in registry.MODULES:
        declared_here |= set(resolve(key).evidence_by_key())
    assert set(PERMANENTLY_UNAVAILABLE) <= declared_here, set(PERMANENTLY_UNAVAILABLE) - declared_here


#: The document's own numbering: a class boundary drifting by one question would silently
#: move a ★ in or out of the reachable region.
_DOC_RANGES: dict[str, tuple[int, int, int]] = {
    "fixed_income": (116, 135, 3),
    "fund": (136, 155, 3),
    "commodity_fund": (156, 165, 2),
    "commodity_certificate": (176, 187, 1),
    "option": (188, 199, 1),
    "future": (200, 211, 2),
    "leveraged_fund": (212, 219, 1),
    "portfolio_allocation": (220, 234, 2),
}


@pytest.mark.parametrize(
    ("instrument", "first", "last", "stoppers"),
    [(key, *bounds) for key, bounds in _DOC_RANGES.items()]
)
def test_each_module_is_the_documents_class_verbatim(
    instrument: str, first: int, last: int, stoppers: int
) -> None:
    rb = resolve(instrument)  # type: ignore[arg-type]
    module_codes = [q.code for q in rb.questions() if int(q.code.split("-")[1]) >= first]

    assert module_codes == [f"PB-{n:03d}" for n in range(first, last + 1)]
    module_questions = [q for q in rb.questions() if q.code in set(module_codes)]
    assert sum(q.stopper for q in module_questions) == stoppers
    assert all(q.text.strip() for q in module_questions)
    # The shared core is composed around the class, never replaced by it.
    assert len(rb.questions()) == (last - first + 1) + 36
    assert [s.id for s in rb.stages()] == list(range(len(rb.stages())))


def test_module_questions_never_reuse_a_stock_code() -> None:
    """PB-001…PB-115 belong to equity; a module that reused one would rewrite a saved sheet."""

    stock = {q.code for q in bank.questions()}
    for key in registry.MODULES:
        if key == "equity":
            continue
        module = registry.MODULES[key]
        assert not {q.code for q in module.questions} & stock, key
