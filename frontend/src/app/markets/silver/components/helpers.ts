export const fa = (n: number | null | undefined): string =>
  n == null || Number.isNaN(n) ? "—" : n.toLocaleString("fa-IR");

export const faPct = (n: number | null | undefined): string =>
  n == null || Number.isNaN(n) ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

export function fmtTr(v?: number): string {
  if (v == null || v === 0) return "—";
  if (v >= 1e12) return (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  return fa(v);
}

export function faDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("fa-IR");
}

export function faDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fa-IR");
}

export function isSilverText(value: unknown): boolean {
  return /نقره|سیلور|silver|xag|ag999|ag925/i.test(String(value ?? ""));
}

export function isGoldText(value: unknown): boolean {
  return /طلا|زر|سکه|gold|xau/i.test(String(value ?? ""));
}

export function metricEntries(metrics: Record<string, unknown>, limit = 4): [string, string][] {
  return Object.entries(metrics)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .slice(0, limit)
    .map(([k, v]) => [k, typeof v === "number" ? (Math.abs(v) >= 1000 ? fa(v) : v.toFixed(4)) : String(v)]);
}
