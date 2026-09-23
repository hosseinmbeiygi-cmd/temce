from __future__ import annotations

from pydantic import Field

from schemas.common.legal import LEGAL_DISCLAIMER_FA

__all__ = ["LEGAL_DISCLAIMER_FA", "LegalDisclaimerMixin"]


class LegalDisclaimerMixin:
    legal_disclaimer: str = Field(default=LEGAL_DISCLAIMER_FA)
