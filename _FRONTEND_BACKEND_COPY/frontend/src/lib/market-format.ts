/**
 * Formatting helpers for the premium market dashboard.
 *
 * Design decision: every numeric display uses **Latin tabular digits**
 * rendered `dir="ltr"` with `font-mono` — this is what gives trading
 * terminals their crisp, aligned, "expensive" look (Persian glyphs in a
 * mono font would fall back and break the tabular alignment). Labels stay
 * fully Persian. All money figures are expressed in میلیارد تومان.
 */

const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Integer with 3-digit thousand separators: 1,234,567 */
export function fmtInt(n: number): string {
  if (!isFinite(n)) return "—";
  return nf0.format(Math.round(n));
}

/** Number with up to `digits` decimals, separator grouped: 12,345.67 */
export function fmtNum(n: number, digits = 2): string {
  if (!isFinite(n)) return "—";
  const f = digits <= 1 ? nf1 : nf2;
  return f.format(n);
}

/** Signed percentage with fixed decimals: +1.25% / -0.84% / 0.00% */
export function fmtPct(n: number, digits = 2): string {
  if (!isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  const body = digits <= 1 ? nf1.format(n) : nf2.format(n);
  return `${sign}${body}%`;
}

/**
 * Value already expressed in میلیارد تومان → grouped with up to `digits`.
 * e.g. 24850.4 → "24,850.4"
 */
export function fmtBillion(n: number, digits = 1): string {
  return fmtNum(n, digits);
}

/** Direction-aware Tailwind text color for a signed value. */
export function dirColor(n: number, positiveClass = "text-up", negativeClass = "text-down"): string {
  if (n > 0) return positiveClass;
  if (n < 0) return negativeClass;
  return "text-ink-3";
}

/** Persian digits for prose contexts (dates, times, counts inside sentences). */
export function faNum(n: number | string): string {
  const s = String(n).replace(/,/g, "");
  return s.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}
