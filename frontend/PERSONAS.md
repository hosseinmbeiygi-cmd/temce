# User Personas — TEMCE

Three personas shape the **interface**, not permissions. The selection is a
persisted UI preference (`temce.persona` in `localStorage`), and roles/access
control remain in `src/lib/auth-context.tsx` + `src/components/RoleGate.tsx`.

| Persona | Persian label | Default view | Emphasis | Refresh | Derivatives | Fundamentals | Order flow | Dense UI |
|---|---|---|---|---|---|---|---|---|
| Retail | خرد | `/markets/gold` | Gold, funds, watchlist, news | 60 s | ✗ | ✗ | ✗ | ✗ |
| Institutional | نهادی | `/portfolio` | Portfolio, fundamentals, options, Codal | 30 s | ✓ | ✓ | ✓ | ✓ |
| Scalper | اسکالپر | `/market-depth` | Order book, heatmap, options chain, signals | 5 s | ✓ | ✗ | ✓ | ✓ |

## Definition

- **Retail (خرد)** — individual investor who wants a simple read of the market:
  gold/coin prices, fund NAVs, their watchlist and headlines. Fewer advanced
  panels; longer polling cadence; an explicit “not investment advice” note.
- **Institutional (نهادی)** — analyst/portfolio manager who decides from
  fundamentals, portfolio composition and derivatives. Denser layout,
  fundamentals and Codal promoted, 30 s refresh.
- **Scalper (اسکالپر)** — short-horizon trader who watches order-book depth,
  queues and option chains. Densest layout, fastest polling (5 s), explicit
  warning that displayed prices lag the source.

## Where it lives

| Piece | File |
|---|---|
| Persona catalog, feature flags, shortcuts | `src/lib/personas.ts` |
| Provider + `usePersona()` (SSR-safe, persists, falls back to Retail) | `src/lib/persona-context.tsx` |
| Navbar selector | `src/components/layout/PersonaSwitcher.tsx` |
| Dashboard strip (label, description, shortcuts, risk note) | `src/components/dashboard/PersonaBar.tsx` |
| Provider mount | `src/app/providers.tsx` |

## Feature flags (per persona)

`denseLayout`, `showDerivatives`, `showFundamentals`, `showOrderFlow`,
`marketRefreshMs`. They are declared and documented now so panels can opt in
with `usePersona().definition.features.<flag>` without introducing a role
system. Changing persona never hides market data that is already on a page; it
changes defaults, shortcuts, labels and polling cadence.
