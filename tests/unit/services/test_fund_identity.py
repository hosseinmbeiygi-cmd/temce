"""Unit tests for canonical fund identity & alias decisions (A2/A8).

تمام تست‌های این فایل Pure هستند (بدون DB / Redis) و منطق تصمیم‌گیری
``decide_identity`` را در همه شاخه‌ها پوشش می‌دهند.
"""

from __future__ import annotations

from services.fund_identity import (
    decide_identity,
    derive_fund_id,
    identity_fingerprint,
    normalize_isin,
    normalize_symbol,
)


def test_normalize_symbol_arabic_and_zwnj():
    assert normalize_symbol("  فولاد\u200cمبارکه  ") == "فولادمبارکه"
    assert normalize_symbol("فولاد\u064a") == "فولادی"  # ي عربی → ی
    assert normalize_symbol("شركت\u0643") == "شرکتک"  # ك عربی → ک
    assert normalize_symbol(None) == ""


def test_normalize_isin():
    assert normalize_isin(" irtk altn0001 ") == "IRTKALTN0001"
    assert normalize_isin("") is None
    assert normalize_isin(None) is None


def test_derive_fund_id_is_stable_when_existing():
    assert derive_fund_id(symbol="آلتون", market="tse") == "tse:آلتون"
    assert derive_fund_id(symbol="آلتون", market="ime") == "ime:آلتون"
    # تغییر نماد با id موجود → id کانونی ثابت می‌ماند
    assert derive_fund_id(symbol="جدید", existing_fund_id="tse:قدیمی") == "tse:قدیمی"


def test_identity_fingerprint_stable_and_sensitive():
    a = identity_fingerprint("IRTKALTN0001", None, "آلتون")
    b = identity_fingerprint("irtkaltn0001", None, "آلتون")
    c = identity_fingerprint("IRXXXX00001", None, "آلتون")
    assert a == b
    assert a != c
    assert len(a) == 40


def test_decide_identity_new_when_no_match():
    d = decide_identity(
        symbol="آلتون",
        isin="IRTKALTN0001",
        national_id=None,
        matches={},
    )
    assert d.action == "new" and d.fund_id is None


def test_decide_identity_same_by_isin():
    d = decide_identity(
        symbol="آلتون",
        isin="IRTKALTN0001",
        national_id=None,
        matches={"by_isin": "tse:آلتون", "by_symbol": "tse:آلتون"},
    )
    assert d.action == "same"
    assert d.fund_id == "tse:آلتون"
    assert d.matched_by == "by_isin"


def test_decide_identity_symbol_changed_when_only_isin_matches():
    d = decide_identity(
        symbol="آلتون۲",
        isin="IRTKALTN0001",
        national_id=None,
        matches={"by_isin": "tse:آلتون"},
    )
    assert d.action == "symbol_changed"
    assert d.fund_id == "tse:آلتون"


def test_decide_identity_same_by_symbol_without_identifiers():
    d = decide_identity(symbol="آلتون", isin=None, national_id=None, matches={"by_symbol": "tse:آلتون"})
    assert d.action == "same" and d.fund_id == "tse:آلتون"
    assert d.matched_by == "by_symbol"


def test_decide_identity_symbol_changed_by_isin():
    d = decide_identity(
        symbol="آلتون۲",
        isin="IRTKALTN0001",
        national_id=None,
        matches={"by_isin": "tse:آلتون", "by_alias": None},
    )
    assert d.action == "symbol_changed"
    assert d.fund_id == "tse:آلتون"
    assert "آلتون۲" in d.aliases_to_add


def test_decide_identity_conflict_symbol_owned_with_other_isin():
    d = decide_identity(
        symbol="آلتون",
        isin="IRFAKE00001",
        national_id=None,
        matches={"symbol_owner": "tse:صندوق‌دیگر"},
    )
    assert d.action == "conflict"
    assert "متعلق" in (d.conflict_reason or "")


def test_decide_identity_conflict_on_strong_identifier_mismatch():
    d = decide_identity(
        symbol="آلتون",
        isin="IRFAKE00001",
        national_id=None,
        matches={
            "by_alias": "tse:آلتون",
            "fund_isin": "IRTKALTN0001",
        },
    )
    assert d.action == "conflict"
    assert "ISIN" in (d.conflict_reason or "")


def test_decide_identity_conflict_national_id_mismatch():
    d = decide_identity(
        symbol="آلتون",
        isin=None,
        national_id="1234567890",
        matches={"by_symbol": "tse:آلتون", "fund_national_id": "9999999999"},
    )
    assert d.action == "conflict"


def test_decide_identity_conflict_when_multi_identities_diverge():
    d = decide_identity(
        symbol="آلتون",
        isin="IRTKALTN0001",
        national_id="1234567890",
        matches={"by_isin": "tse:آلتون", "by_alias": "tse:آلتون۲"},
    )
    assert d.action == "conflict"


def test_decide_identity_enrichment_allowed_when_stored_isin_empty():
    d = decide_identity(
        symbol="آلتون",
        isin="IRTKALTN0001",
        national_id=None,
        matches={"by_symbol": "tse:آلتون", "fund_isin": None},
    )
    assert d.action == "same"
