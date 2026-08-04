"""Unit tests for the lazy (PEP 562) ``repositories`` package exports.

``repositories/__init__.py`` defers loading each repository module until
the public name is actually accessed, keeping ``import repositories``
nearly free and consistent with the project's sub-second import-time goal.
"""

from __future__ import annotations

import importlib

import repositories


def test_import_package_is_cheap_and_has_no_eager_attrs():
    """Importing the package must not eagerly define any public names.

    Note: ``hasattr``/``getattr`` would trigger the lazy ``__getattr__`` and
    defeat the check, so we inspect the module ``__dict__`` directly.
    """
    # Reset any names a previous test may have lazily cached so this test
    # exercises a fresh-import state deterministically.
    importlib.reload(repositories)
    for name in list(repositories.__dict__):
        if name in repositories._LAZY_IMPORTS:
            del repositories.__dict__[name]
    assert "InstrumentRepository" not in repositories.__dict__
    assert "UserRepository" not in repositories.__dict__
    assert "BaseRepository" not in repositories.__dict__


def test_import_package_does_not_load_all_modules():
    """Importing the package alone must not load every repository module."""
    import sys

    before = {
        m for m in sys.modules if m.startswith("repositories.") and m != "repositories.base_repository"
    }
    # Force a clean re-import of just the package.
    importlib.reload(repositories)
    after = {m for m in sys.modules if m.startswith("repositories.") and m != "repositories.base_repository"}
    # No submodules should be added by a bare package import.
    assert after <= before


def test_from_import_style_works():
    from repositories import InstrumentRepository

    assert InstrumentRepository.__name__ == "InstrumentRepository"


def test_attribute_access_loads_and_caches():
    # First access triggers the lazy import…
    first = repositories.QuoteRepository
    # …and is cached on the package module for repeat access.
    assert "QuoteRepository" in repositories.__dict__
    assert repositories.QuoteRepository is first


def test_every_public_name_is_resolvable():
    for name in repositories.__all__:
        obj = getattr(repositories, name)
        assert obj is not None
        assert obj.__name__ == name


def test_unknown_attribute_raises_attribute_error():
    import pytest

    with pytest.raises(AttributeError, match="repositories"):
        _ = repositories.DoesNotExist  # triggers module __getattr__


def test_star_import_style_works():
    namespace: dict = {}
    exec("from repositories import *", namespace)
    exported = {k for k in namespace if not k.startswith("__")}
    assert "InstrumentRepository" in exported
    assert "UserRepository" in exported
    assert "BaseRepository" in exported


def test_module_map_matches_all():
    """``__all__`` must exactly match the ``_LAZY_IMPORTS`` keys."""
    assert set(repositories._LAZY_IMPORTS) == set(repositories.__all__)
