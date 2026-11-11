"""Symbol extraction from news text must be catalog-driven, not a fixed cap.

``NewsParser.extract_symbols`` feeds ``NewsIngestionService._save_article``
(the ``symbols=`` column on the news row and the dual-write tags), so a
hard-coded candidate list silently under-tags every article about a symbol
outside it — the removal reason never surfaces anywhere.

Contract pinned here (no DB, no network):

* only symbols that exist in the static catalog may be returned;
* a bare mention needs a token boundary — prose words that happen to be
  catalog tickers (``کالا`` in «بورس کالا») must not become symbols;
* a look-alike symbol must not be attached to a longer symbol's mention;
* order follows first appearance, duplicates collapse.
"""

from __future__ import annotations


def _parser():
    from providers.news.parser import NewsParser

    return NewsParser()


def test_tickers_outside_the_legacy_six_are_extracted() -> None:
    """``شبندر``/``وبملت`` were invisible to the old 6-symbol list."""
    parser = _parser()

    found = parser.extract_symbols("افزایش سرمایه شبندر و رشد سود وبملت در گزارش امروز")

    assert "شبندر" in found
    assert "وبملت" in found


def test_order_follows_first_appearance_and_duplicates_collapse() -> None:
    parser = _parser()

    found = parser.extract_symbols("فملی صعود کرد؛ فولاد افت کرد؛ فملی دوباره صعود")

    assert found == ["فملی", "فولاد"]


def test_cashtag_matches_any_catalog_symbol_including_funds() -> None:
    """An explicit ``#ticker`` is unambiguous, so the full catalog applies."""
    parser = _parser()

    found = parser.extract_symbols("سود #آگاس و #آسامید اعلام شد")

    assert "آگاس" in found
    assert "آسامید" in found


def test_ambiguous_generic_prose_word_is_not_a_symbol() -> None:
    """«بورس کالا» is the exchange, not a ticker mention."""
    parser = _parser()

    found = parser.extract_symbols("حجم معاملات بورس کالا و ارزش معاملات افزایش یافت")

    assert "کالا" not in found


def test_unknown_text_yields_no_symbols() -> None:
    parser = _parser()

    assert parser.extract_symbols("شاخص کل بورس با رشد همراه بود") == []
    assert parser.extract_symbols("") == []


def test_arabic_spelling_variant_resolves_to_the_catalog_symbol() -> None:
    """Persian/Arabic ي/ك spellings must fold before the catalog lookup, and
    the canonical Persian spelling is what gets returned."""
    parser = _parser()

    found = parser.extract_symbols("نماد فملي و فايرا امروز صف خريد داشتند")

    assert "فملی" in found
    assert "فایرا" in found


def test_spelling_twins_collapse_to_the_persian_canonical_form() -> None:
    """``آسامید``/``آساميد`` are one fund — one hit, Persian spelling."""
    parser = _parser()

    found = parser.extract_symbols("سود #آساميد و #آسامید تقسیم شد")

    assert found == ["آسامید"]


def test_repeated_mentions_of_one_ticker_are_reported_once() -> None:
    parser = _parser()

    found = parser.extract_symbols("فولاد صعود کرد؛ #فولاد امروز صف خرید داشت")

    assert found == ["فولاد"]


def test_lookalike_symbol_is_not_truncated_to_its_shorter_twin() -> None:
    """``کگل2`` must not be reported as ``کگل`` (wrong symbol attached)."""
    parser = _parser()

    found = parser.extract_symbols("نماد کگل2 با افزایش تقاضا مواجه شد")

    assert found == ["کگل2"]


def test_latin_symbol_requires_a_token_boundary() -> None:
    parser = _parser()

    assert "BTC" in parser.extract_symbols("قیمت BTC امروز رشد کرد")
    assert "BTC" not in parser.extract_symbols("نماد ABTCX در بازار نیست")


def test_every_returned_symbol_exists_in_the_catalog() -> None:
    from domain.instruments import symbol_catalog

    parser = _parser()
    text = (
        "فولاد، شپنا، شبندر، وبملت، آگاس، BTC، XAUUSD و کگل2 در گزارش امروز "
        "بورس کالا و ارزش معاملات شرکت ناشناخته فلان"
    )
    catalog = {row["symbol"] for row in symbol_catalog.all_symbols()}

    found = parser.extract_symbols(text)

    assert found, "the sample text must exercise the extractor"
    assert set(found) <= catalog


def test_symbols_per_article_are_capped() -> None:
    """A market round-up must not tag (and later notify on) every ticker."""
    from providers.news.parser import MAX_SYMBOLS_PER_ARTICLE

    parser = _parser()
    text = "فولاد شپنا شبندر وبملت فملی خودرو پارس کگل2 فایرا BTC XAUUSD"

    found = parser.extract_symbols(text)

    assert len(found) == MAX_SYMBOLS_PER_ARTICLE == 8
    # First-appearance order is preserved for the kept mentions.
    assert found[:4] == ["فولاد", "شپنا", "شبندر", "وبملت"]
    assert "BTC" not in found and "XAUUSD" not in found
