# Gold Team — Dependency Requests

This file lists new pip/npm dependencies proposed by the gold-team fix branch.
Each entry requires explicit owner approval before the package is added to
`requirements.txt` and installed.

---

## WS4: `feedparser` (approved via gate "WS4")

| Field | Value |
|-------|-------|
| **Package** | `feedparser` |
| **Version constraint** | `>=6.0,<7` |
| **License** | BSD 2-Clause ("Simplified BSD License") — permissive, no copyleft |
| **Purpose** | Parse RSS/Atom feeds from Persian financial news sites (BoursePress, EghtesadNews, ISNA, etc.) in `services/chat/news_fetcher.py` |
| **Why not already installed** | PHASE0 audit found the import already guarded by `try/except ImportError`; `HAS_FEEDPARSER=False` silently disables all RSS fetching |
| **Approval** | Owner typed "WS4" after gate "بله (licensing)" was shown — RSS licensing (public feeds, no authentication required) confirmed |
| **Added to** | `requirements.txt` |
