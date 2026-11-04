"""Settings must load the repository `.env` without manual preprocessing.

Regression for the real file: values carry inline ``#`` comments and
``CORS_ORIGINS`` is a JSON list on one line.  ``Settings`` must parse those
directly — no test-side stripping, no custom ``dotenv`` pass.
"""

from __future__ import annotations

from pathlib import Path

from core.config import Settings

FIXTURE = Path(__file__).parent / "fixtures" / "env_parsing.env"


def _load_fixture(monkeypatch) -> Settings:
    # The developer's shell may already export these; a fixture file must win
    # over an inherited value that would mask the parser.
    for key in (
        "ENV",
        "DEBUG",
        "SECRET_KEY",
        "CORS_ORIGINS",
        "DATABASE_URL",
        "ML_MODEL_DIR",
        "AUTH_DISABLED",
        "DEFAULT_CURRENCY",
    ):
        monkeypatch.delenv(key, raising=False)
    return Settings(_env_file=FIXTURE)


def test_quoted_cors_list_and_inline_comments_are_parsed(monkeypatch) -> None:
    settings = _load_fixture(monkeypatch)

    assert settings.environment == "staging"
    assert settings.debug is True
    assert settings.secret_key == "quoted-secret-key"
    assert settings.cors_origins == [
        "https://app.example",
        "https://www.example",
    ]
    assert settings.ml_model_dir == "./ml_artifacts"
    assert settings.default_currency == "TOMAN"


def test_cors_origins_accepts_comma_separated_values(monkeypatch) -> None:
    """Operators often write a bare comma list; it must not need JSON."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings(
        _env_file=None,
        CORS_ORIGINS="https://one.example, https://two.example  # note",
    )

    assert settings.cors_origins == [
        "https://one.example",
        "https://two.example",
    ]


def test_cors_origins_accepts_quoted_single_string(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings(
        _env_file=None,
        CORS_ORIGINS="'https://only.example'",
    )

    assert settings.cors_origins == ["https://only.example"]


def test_gold_risk_config_defaults(monkeypatch) -> None:
    """The new history guards are configurable and safe by default."""
    monkeypatch.delenv("GOLD_BUBBLE_MIN_OBSERVATIONS", raising=False)
    monkeypatch.delenv("GOLD_DXY_MIN_SAMPLES", raising=False)

    settings = Settings(_env_file=None)

    assert settings.gold_bubble_min_observations == 30
    assert settings.gold_dxy_min_samples == 30
    assert settings.gold_dxy_percentile_low == 20.0
    assert settings.gold_dxy_percentile_high == 80.0
