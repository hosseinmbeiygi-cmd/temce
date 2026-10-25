# Plan: GoldDesk Frontend Analysis Report (`docs/analysis/03_frontend.md`)

## Context

The user (senior frontend/UX analyst) requires a comprehensive Persian report on the GoldDesk frontend. Output goes to `docs/analysis/03_frontend.md`. No source files may be modified.

## Scope

- **In scope:** `frontend/src/app/gold/**`, `frontend/src/components/gold/**`, `frontend/src/app/gold/components/**`, `frontend/src/lib/goldApi.ts`, `frontend/src/lib/api.ts`, `frontend/src/types/gold.ts`, `frontend/public/golddesk-manifest.json`, `frontend/public/golddesk-sw.js`, `frontend/package.json`, `frontend/src/__tests__/**`, `frontend/src/app/globals.css`.
- **Out of scope (read-only cross-check only):** `src/gold_desk/*`, `apps/api/*`, backend code, DB schema, Python scripts.
- **Language:** Persian (فارسی) with English technical terms preserved inline.

## Report structure (12 mandatory sections)

1. صفحه‌ها و معماری ناوبری (Pages & navigation architecture)
2. کاتالوگ کامپوننت‌ها (Component catalog)
3. لایه API و تایپینگ (API layer & typing)
4. PWA و سرویس ورکر (PWA & service worker)
5. تم‌ها و دسترسی‌پذیری (Themes & accessibility)
6. اعتماد، امنیت و تجربه کاربری (Trust, security, UX)
7. عملکرد و بهینه‌سازی (Performance & optimization)
8. تست‌ها (Tests)
9. مستندات و حاصل‌های فنی (Docs audit)
9. وابستگی‌ها (Dependencies)
10. رابط‌های ورودی/خروجی API (API endpoints)
11. معماری داده و جریان داده (Data architecture & flow)
12. خلاصه و پیشنهادات اصلاحی (Summary & remediation)

## Required labeling convention

Every claim must be labeled:
- `[کد]` — verified directly from source code, anchored to `file:line`
- `[استنباط]` — inferred from code patterns, not directly visible
- `[پیشنهاد]` — recommendation for improvement

Unverified claims must be marked "مشاهده نشد".

## Key findings to include (already verified)

- 13 tabs in `frontend/src/app/gold/layout.tsx:14-30`.
- Duplicate `CoinBubbleTable` component: `frontend/src/app/gold/components/CoinBubbleTable.tsx` vs `frontend/src/components/gold/CoinBubbleTable.tsx` (different prop signatures).
- Typo `کمی偏离` at `frontend/src/components/gold/ParityBadge.tsx:18`.
- Auth inconsistency: `frontend/src/app/gold/tokens/page.tsx:15-34` uses raw `fetch()` instead of shared API client.
- **Critical:** `--gd-*` CSS variables (`--gd-bg`, `--gd-bg-2`, `--gd-bg-3`, `--gd-border`, `--gd-text`, `--gd-text-2`, `--gd-text-3`, `--gd-accent`, `--gd-accent-2`, `--gd-success`, `--gd-warn`, `--gd-danger`) are referenced by ~40+ inline styles across gold pages but are **never defined** in the working `frontend/src/app/globals.css`. The theme block that defines them (`[data-theme="dark"]`, `[data-theme="light"]`, `[data-theme="gold"]`) exists in the reference tree at `.freebuff/worktrees/.../_FRONTEND_BACKEND_COPY/frontend/src/app/globals.css:1805-1866` but is absent from the working copy (2014 lines, ends at `.gold-main` rule at line 2006-2014). `ThemeProvider.tsx:31` sets `data-theme` but no CSS consumes it for `--gd-*`. Result: gold pages render with broken/unresolved CSS variables in production.
- 3 test files covering snapshot, derivatives risk, macro/options; no tests for layout, tokens, PWA, chat, health, antigravity.
- SW caching strategy and cache name versions in `frontend/public/golddesk-sw.js`.

## Verification steps for the implementing agent

1. Re-confirm `--gd-*` absence: `grep -rn "\-\-gd-" frontend/src/app/globals.css` should return nothing.
2. Re-confirm consumers: `grep -rn "var(--gd-" frontend/src/app/gold frontend/src/components/gold` to count references.
3. Confirm the reference tree path `.freebuff/worktrees/72c673be-fb1e-40c5-b73b-0d2101b6247a/_FRONTEND_BACKEND_COPY/frontend/src/app/globals.css` lines 1805-1866 contain the missing theme block.
4. Cross-check every `goldApi.ts` endpoint against backend route definitions before writing section 10.

## Deliverable

Write `docs/analysis/03_frontend.md` with the 12 sections above, all claims labeled `[کد]`/`[استنباط]`/`[پیشنهاد]`, anchored to `file:line`. Mark unverified items "مشاهده نشد". Do not modify any source files.