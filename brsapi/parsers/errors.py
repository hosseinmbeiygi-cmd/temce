"""Parse-error contract for BrsApi response parsers.

A parser that returns an empty list is saying "the provider answered and it has
nothing for us". That return value must not stand for "we could not read the
response": a payload whose shape the parser does not understand raises
:class:`BrsApiParseError`, so ``BrsApiSyncService`` can record a failed sync
instead of a successful one with ``items_count=0``.

Each error carries a machine-readable ``code`` so callers never have to infer
the failure from the message text.

The provider also answers "nothing right now" with a JSON envelope instead of
an empty array. :func:`is_no_data` recognises those envelopes so every parser
draws the same line between "no rows today" and "a response we cannot read".
"""

from __future__ import annotations

from typing import Any, Literal

ParseFailureCode = Literal[
    "unexpected_shape",  # top-level value is not the list/dict the parser reads
    "unrecognised_envelope",  # an envelope we know nothing about (no known keys)
    "missing_payload",  # no payload at all (``None``)
]

# Keys that only ever carry provider metadata, never rows. A dict made of
# nothing but these is an answer without data, e.g.
# ``{"code_http": 200, "successful": true, "message_error": null}``.
PROVIDER_ENVELOPE_KEYS = frozenset(
    {"status", "code_http", "successful", "message_error", "message"}
)


class BrsApiParseError(ValueError):
    """The payload did not have the shape the parser understands.

    Subclasses :class:`ValueError` because the value itself — not the transport
    or the credentials — is wrong; existing ``except ValueError`` handlers keep
    working while callers that care can catch this type precisely.
    """

    def __init__(
        self,
        message: str,
        *,
        code: ParseFailureCode = "unexpected_shape",
    ) -> None:
        self.code: ParseFailureCode = code
        super().__init__(message)


def is_no_data(data: Any) -> bool:
    """True when the payload is a valid "nothing to report" answer.

    Recognised shapes:

    * ``[]`` / ``{}`` — the provider answered with nothing
    * ``{"status": "no_data"}`` — BrsApi's explicit no-data marker
    * a metadata-only envelope such as
      ``{"code_http": 200, "successful": true, "message_error": null}``

    Anything else (a scalar, or a dict naming keys the parser does not know) is
    **not** no-data: the caller either understands it or raises.
    """
    if isinstance(data, list):
        return not data
    if isinstance(data, dict):
        if not data:
            return True
        if data.get("status") == "no_data":
            return True
        return set(data) <= PROVIDER_ENVELOPE_KEYS
    return False


def ensure_payload(data: Any, name: str) -> None:
    """Raise ``missing_payload`` when there is no payload at all."""
    if data is None:
        raise BrsApiParseError(
            f"{name}: payload is None, not a JSON document",
            code="missing_payload",
        )
