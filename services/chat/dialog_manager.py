"""DialogManager — Conversation context and state management (Level 8).

Provides:
- Multi-turn conversation context tracking
- Slot filling across turns
- Context window management
- Entity resolution with context
- Conversation history
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class DialogTurn:
    """A single turn in the conversation."""

    def __init__(
        self,
        user_message: str,
        intent: str,
        entities: dict[str, Any],
        response: dict[str, Any],
        confidence: float = 0.0,
    ):
        self.user_message = user_message
        self.intent = intent
        self.entities = entities
        self.response = response
        self.confidence = confidence
        self.timestamp = time.time()


class DialogManager:
    """Manage conversation context across multiple turns."""

    def __init__(self, max_history: int = 10, context_ttl: int = 600):
        self._max_history = max_history
        self._context_ttl = context_ttl  # 10 minutes
        # user_id -> OrderedDict of turns
        self._sessions: dict[str, OrderedDict] = {}

    def _get_session(self, user_id: str) -> OrderedDict:
        """Get or create a session for a user."""
        if user_id not in self._sessions:
            self._sessions[user_id] = OrderedDict()
        return self._sessions[user_id]

    def add_turn(
        self,
        user_id: str,
        user_message: str,
        intent: str,
        entities: dict[str, Any],
        response: dict[str, Any],
        confidence: float = 0.0,
    ) -> None:
        """Add a turn to the conversation history."""
        session = self._get_session(user_id)
        turn_id = f"turn_{int(time.time() * 1000)}"
        session[turn_id] = DialogTurn(
            user_message=user_message,
            intent=intent,
            entities=entities,
            response=response,
            confidence=confidence,
        )

        # Enforce max history
        while len(session) > self._max_history:
            session.popitem(last=False)

        # Clean expired sessions
        self._clean_expired()

    def get_history(self, user_id: str) -> list[DialogTurn]:
        """Get conversation history for a user."""
        session = self._get_session(user_id)
        now = time.time()
        valid = []
        for turn_id, turn in list(session.items()):
            if now - turn.timestamp < self._context_ttl:
                valid.append(turn)
            else:
                del session[turn_id]
        return valid

    def get_last_turn(self, user_id: str) -> DialogTurn | None:
        """Get the most recent turn."""
        history = self.get_history(user_id)
        return history[-1] if history else None

    def get_last_intent(self, user_id: str) -> str | None:
        """Get the intent of the last turn."""
        turn = self.get_last_turn(user_id)
        return turn.intent if turn else None

    def get_context(self, user_id: str) -> dict[str, Any]:
        """Get aggregated context from conversation history."""
        history = self.get_history(user_id)
        if not history:
            return {
                "current_symbols": [],
                "last_intent": None,
                "last_entities": {},
                "mentioned_symbols": [],
                "recent_intents": [],
                "turn_count": 0,
            }

        # Collect all mentioned symbols
        all_symbols = []
        recent_intents = []
        for turn in history[-5:]:  # Last 5 turns
            symbols = turn.entities.get("symbols", [])
            all_symbols.extend(symbols)
            recent_intents.append(turn.intent)

        # Remove duplicates while preserving order
        seen = set()
        unique_symbols = []
        for s in all_symbols:
            if s not in seen:
                seen.add(s)
                unique_symbols.append(s)

        last = history[-1]

        return {
            "current_symbols": unique_symbols[:5],
            "last_intent": last.intent,
            "last_entities": last.entities,
            "mentioned_symbols": unique_symbols,
            "recent_intents": recent_intents,
            "turn_count": len(history),
        }

    def resolve_symbol(
        self, user_id: str, text: str, extracted_symbols: list[str]
    ) -> list[str]:
        """Resolve symbols using context if not found in current text."""
        if extracted_symbols:
            return extracted_symbols

        # Try to find symbols from context
        context = self.get_context(user_id)
        mentioned = context.get("mentioned_symbols", [])

        # Check if text refers to "همین سهم", "این نماد", etc.
        if any(ref in text for ref in ["این", "همین", "همون", "قبلی", "همان"]):
            last_turn = self.get_last_turn(user_id)
            if last_turn:
                return last_turn.entities.get("symbols", [])

        return mentioned[:1] if mentioned else []

    def resolve_filter(self, user_id: str, conditions: list[dict]) -> list[dict]:
        """Resolve filter conditions using context if not specified."""
        if conditions:
            return conditions
        return []

    def _clean_expired(self) -> None:
        """Remove expired sessions."""
        now = time.time()
        expired_users = []
        for user_id, session in self._sessions.items():
            # Check if all turns in session are expired
            if session:
                last_turn = next(reversed(session.values()))
                if now - last_turn.timestamp > self._context_ttl:
                    expired_users.append(user_id)
            else:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self._sessions[user_id]

    def clear_session(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        if user_id in self._sessions:
            del self._sessions[user_id]
