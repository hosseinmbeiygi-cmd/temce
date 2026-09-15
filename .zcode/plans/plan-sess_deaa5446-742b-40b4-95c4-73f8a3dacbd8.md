Replace `frontend/src/app/markets/silver/page.tsx` (currently `test ok`) with a full live silver-market view matching the Rahavard-style reference the user pasted.

# File
- Edit: `frontend/src/app/markets/silver/page.tsx` (one file, ~280 lines)

# Stack
- "use client" + React + @tanstack/react-query
- AppLayout from `@/components/layout/AppLayout` (consistent with sibling pages)
- apiGet, extractArray from `@/lib/api`
- lucide-react icons (Coins, TrendingUp, TrendingDown, Newspaper, BarChart3, DollarSign, Clock, Sparkles, AlertTriangle, Calendar)
- local format helpers (formatPrice, formatPct)

# Data sources (all parallel useQuery)
1. `GET /api/v1/brsapi/gold-coin` → silver 999/925/شمش items (filter name contains "نقره" or "شمش نقره")
2. `GET /api/v1/brsapi/currency` → USD price for converter
3. `GET /api/v1/funds?fund_type=نقره&limit=50` → silver ETFs (نقراط, سیگلو, پلاتا, سیمین, ...)
4. `GET /api/v1/gold/ime/futures` → آتی نقره contracts
5. `GET /api/v1/news?category=market&page_size=8` → news strip
6. `GET /api/v1/market-dashboard` → heatmap cells for ETF grid

Mock fallback per section (commodity pattern: try API → catch → mock[]), so page never blank if backend hiccups.

# Sections (in order)
1. **Hero** — purple/silver gradient backdrop, status pill, title + subtitle, 4 hero stat cards (انس USD, نقره 999 IRR, شاخص صندوق‌ها, دلار)
2. **Live silver prices grid** — 4-col responsive grid of silver 999/925/شمش cards with % change badge + sparkline placeholder
3. **Silver ETFs table (مشتقات و صندوق‌ها)** — columns: name, last_price, change%, trade_value, market_value, nav_change_pct, bubble-pct; click row → /funds/{symbol}
4. **Futures table (آتی نقره)** — columns: symbol, delivery_date, last_price, change%, volume, open_interest (from /gold/ime/futures)
5. **Converter** — input grams → USD × ounce / 31.1035 → IRR (uses live دلار + live نقره 999)
6. **News strip** — top 6 news titles with sentiment dot
7. **API info card** — small, lists the 5 endpoints used + 30s/60s refetch intervals
8. **Disclaimer footer** — AlertTriangle + نکته: داده‌ها نمایشی

# Layout pattern
Reuse commodity/page.tsx style: glass-card, `bg-surface-800/80`, `border-surface-700`, fa-IR numerals, accent-emerald/rose for up/down, font-mono for prices.

# Skipped (deliberate, with ceiling)
- Social/discussion posts feed — no endpoint in backend (chat = AI bot, not social)
- Online platforms table — no backend source
- Certificate-of-deposit (گواهی سپرده) table — no dedicated endpoint
- Calculator with حباب % and full محاسبه‌گر — single-purpose converter only; full multi-field calculator add when needed
- Sparklines — requires /market/sparklines per-symbol call; add when news/UX demands
- Bubbles / treemap heatmap — replace later with BubbleHeatmap when filter param exists
- Silver ounce chart (TradingView) — same gold-fx pattern, add when chart wrapper confirmed stable

# Self-check
Manual smoke after dev-server hot-reload: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/markets/silver` should return 200, no console `ReferenceError`.

# Trade-offs
- Single file (no new components) — keeps diff minimal, follows sibling pattern
- Mock fallback per query — page stays useful when backend down (matches commodity pattern)
- Persian UI copy from user paste, kept verbatim where domain-specific (نقره گرمی 999, شمش نقره, صندوق‌های نقره)