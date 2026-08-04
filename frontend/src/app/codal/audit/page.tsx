"use client";
import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import Skeleton from "@/components/Skeleton";

type AuditRow = {
  symbol: string; report_type: string | null; report_date: string | null;
  revenue: number | null; net_profit: number | null; total_assets: number | null; total_equity: number | null; eps: number | null;
  roe: number | null; roa: number | null; gross_margin: number | null; net_margin: number | null;
  current_ratio: number | null; debt_to_equity: number | null; asset_turnover: number | null;
  revenue_growth: number | null; net_profit_growth: number | null;
  health_score: number | null; health_classification: string | null;
  earnings_quality_score: number | null; forensic_risk: string | null;
  total_reports: number; analysis_status: string;
};

interface HealthDistRow { health_classification: string; cnt: number; avg_score: number; }
interface TopRoeRow { symbol: string; roe: number; net_margin: number; health_score: number; health_classification: string; }
interface AuditStatsData { health_distribution: HealthDistRow[]; top_roe: TopRoeRow[]; }

function fmt(v: number | null, pct = false): string {
  if (v === null || v === undefined) return "-";
  if (pct) return (v * 100).toFixed(1) + "%";
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1) + "Mrd";
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v.toFixed(2);
}

function hc(c: string | null): string {
  if (c === "Strong") return "text-green-400 bg-green-400/10";
  if (c === "Stable") return "text-blue-400 bg-blue-400/10";
  if (c === "Watchlist") return "text-yellow-400 bg-yellow-400/10";
  if (c === "Risky") return "text-red-400 bg-red-400/10";
  return "text-gray-400 bg-gray-400/10";
}

function hl(c: string | null): string {
  if (c === "Strong") return "قوي";
  if (c === "Stable") return "پايدار";
  if (c === "Watchlist") return "نگاه";
  if (c === "Risky") return "پرخطر";
  return c || "-";
}

export default function CodalAuditPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [health, setHealth] = useState("");
  const [sortBy, setSortBy] = useState("health_score");
  const [sortDir, setSortDir] = useState("desc");
  const [sel, setSel] = useState<string | null>(null);
  const [tab, setTab] = useState<"table" | "stats">("table");

  const { data: summary, isLoading: sLoad } = useQuery({
    queryKey: ["ca-sum", page, search, health, sortBy, sortDir],
    queryFn: () => apiGet<{ data?: { items?: AuditRow[]; total?: number; total_pages?: number } }>("/codal-audit/summary?page=" + page + "&page_size=50&search=" + search + "&health=" + health + "&sort_by=" + sortBy + "&sort_dir=" + sortDir),
  });

  const { data: stats, isLoading: stLoad } = useQuery({
    queryKey: ["ca-stats"],
    queryFn: () => apiGet<{ data?: AuditStatsData }>("/codal-audit/stats"),
  });

  const { data: sym, isLoading: symLoad } = useQuery({
    queryKey: ["ca-sym", sel],
    queryFn: () => apiGet<{ data?: AuditRow }>("/codal-audit/symbol/" + sel),
    enabled: !!sel,
  });

  const rows: AuditRow[] = summary?.data?.items || [];
  const total = summary?.data?.total || 0;
  const tp = summary?.data?.total_pages || 1;
  const sd = stats?.data || null;

  const th = (label: string, key: string) => (
    <th className="py-3 px-4 text-right font-medium cursor-pointer hover:text-white" onClick={() => { setSortBy(key); setSortDir(sortDir === "desc" ? "asc" : "desc"); }}>{label}</th>
  );

  return (
    <AppLayout title="حسابرسی کدال" subtitle="تحليل مالي تمام نمادها بر اساس گزارش‌هاي کدال">
      <div className="space-y-6">
        <div className="flex gap-2">
          <button onClick={() => setTab("table")} className={"px-4 py-2 rounded-lg text-sm font-medium transition " + (tab === "table" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-300 hover:bg-surface-700")}>جدول نمادها</button>
          <button onClick={() => setTab("stats")} className={"px-4 py-2 rounded-lg text-sm font-medium transition " + (tab === "stats" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-300 hover:bg-surface-700")}>آمار کلی</button>
        </div>

        {tab === "stats" && sd && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {sd.health_distribution.map((h: HealthDistRow) => (
                <div key={h.health_classification} className="bg-surface-800 rounded-xl p-4 border border-surface-700">
                  <div className={"text-sm font-medium " + hc(h.health_classification).split(" ")[0]}>{hl(h.health_classification)}</div>
                  <div className="text-2xl font-bold text-white mt-1">{h.cnt}</div>
                  <div className="text-xs text-surface-400">ميانگين: {fmt(h.avg_score)}</div>
                </div>
              ))}
            </div>
            <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
              <h3 className="text-lg font-bold text-white mb-4">بيشترين بازده حقوق صاحبان سهام</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="text-surface-400 border-b border-surface-700">
                    <th className="py-2 text-right">نماد</th><th className="py-2 text-right">ROE</th><th className="py-2 text-right">حاشيه سود</th><th className="py-2 text-right">امتياز</th><th className="py-2 text-right">وضعيت</th>
                  </tr></thead>
                  <tbody>
                    {sd.top_roe.map((r: TopRoeRow) => (
                      <tr key={r.symbol} className="border-b border-surface-700/50 hover:bg-surface-700/30 cursor-pointer" onClick={() => setSel(r.symbol)}>
                        <td className="py-2 text-white font-medium">{r.symbol}</td>
                        <td className="py-2 text-green-400">{fmt(r.roe)}</td>
                        <td className="py-2 text-surface-300">{fmt(r.net_margin, true)}</td>
                        <td className="py-2 text-surface-300">{fmt(r.health_score)}</td>
                        <td className="py-2"><span className={"px-2 py-0.5 rounded text-xs " + hc(r.health_classification)}>{hl(r.health_classification)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {tab === "table" && (
          <>
            <div className="flex flex-wrap gap-3 items-center">
              <input type="text" placeholder="جستجوي نماد..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-sm text-white placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500 w-48" />
              <select value={health} onChange={(e) => { setHealth(e.target.value); setPage(1); }} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none">
                <option value="">همه وضعيت‌ها</option>
                <option value="Strong">قوي</option>
                <option value="Stable">پايدار</option>
                <option value="Watchlist">نگاه</option>
                <option value="Risky">پرخطر</option>
              </select>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none">
                <option value="health_score">امتياز سلامت</option>
                <option value="roe">بازده حقوق</option>
                <option value="net_margin">حاشيه سود خالص</option>
                <option value="current_ratio">نسبت جاري</option>
                <option value="debt_to_equity">نسبت بدهي</option>
                <option value="revenue">درآمد</option>
              </select>
              <button onClick={() => setSortDir(sortDir === "desc" ? "asc" : "desc")} className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-white hover:bg-surface-700">{sortDir === "desc" ? "↓" : "↑"}</button>
              <span className="text-surface-400 text-sm">{total} نماد</span>
            </div>
            {sLoad ? <Skeleton className="h-96" /> : (
              <div className="bg-surface-800 rounded-xl border border-surface-700 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="text-surface-400 bg-surface-900/50">
                      {th("نماد", "symbol")}{th("وضعيت", "health_score")}{th("ROE", "roe")}{th("حاشيه سود", "net_margin")}
                      <th className="py-3 px-4 text-right font-medium">نسبت جاري</th><th className="py-3 px-4 text-right font-medium">D/E</th>
                      {th("درآمد", "revenue")}{th("سود خالص", "net_profit")}{th("رشد", "revenue_growth")}
                    </tr></thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.symbol} className="border-t border-surface-700/50 hover:bg-surface-700/30 cursor-pointer transition" onClick={() => setSel(r.symbol)}>
                          <td className="py-3 px-4 text-white font-medium">{r.symbol}</td>
                          <td className="py-3 px-4"><span className={"px-2 py-0.5 rounded text-xs font-medium " + hc(r.health_classification)}>{hl(r.health_classification)}</span></td>
                          <td className="py-3 px-4 text-green-400 font-mono">{fmt(r.roe)}</td>
                          <td className="py-3 px-4 text-surface-300 font-mono">{fmt(r.net_margin, true)}</td>
                          <td className="py-3 px-4 text-surface-300 font-mono">{fmt(r.current_ratio)}</td>
                          <td className="py-3 px-4 text-surface-300 font-mono">{fmt(r.debt_to_equity)}</td>
                          <td className="py-3 px-4 text-surface-300 font-mono">{fmt(r.revenue)}</td>
                          <td className="py-3 px-4 font-mono">{r.net_profit && r.net_profit > 0 ? <span className="text-green-400">{fmt(r.net_profit)}</span> : r.net_profit && r.net_profit < 0 ? <span className="text-red-400">{fmt(r.net_profit)}</span> : <span className="text-surface-500">-</span>}</td>
                          <td className="py-3 px-4 font-mono">{r.revenue_growth !== null ? <span className={r.revenue_growth > 0 ? "text-green-400" : "text-red-400"}>{fmt(r.revenue_growth, true)}</span> : <span className="text-surface-500">-</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex justify-between items-center px-4 py-3 bg-surface-900/30 border-t border-surface-700">
                  <span className="text-surface-400 text-sm">صفحه {page} از {tp}</span>
                  <div className="flex gap-2">
                    <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded bg-surface-700 text-white text-sm disabled:opacity-50 hover:bg-surface-600">قبلی</button>
                    <button disabled={page >= tp} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded bg-surface-700 text-white text-sm disabled:opacity-50 hover:bg-surface-600">بعدی</button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {sel && (
          <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setSel(null)}>
            <div className="bg-surface-800 rounded-2xl border border-surface-700 max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">{sel}</h2>
                <button onClick={() => setSel(null)} className="text-surface-400 hover:text-white text-2xl">&times;</button>
              </div>
              {symLoad ? <Skeleton className="h-48" /> : sym?.data && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <span className={"px-3 py-1 rounded-lg text-sm font-medium " + hc(sym.data.health_classification)}>{hl(sym.data.health_classification)}</span>
                    <span className="text-surface-400">امتياز: {fmt(sym.data.health_score)}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {[["درآمد", fmt(sym.data.revenue)], ["سود خالص", fmt(sym.data.net_profit)], ["دارايي", fmt(sym.data.total_assets)], ["ROE", fmt(sym.data.roe)], ["ROA", fmt(sym.data.roa)], ["حاشيه سود", fmt(sym.data.net_margin, true)], ["حاشيه ناخالص", fmt(sym.data.gross_margin, true)], ["نسبت جاري", fmt(sym.data.current_ratio)], ["D/E", fmt(sym.data.debt_to_equity)], ["رشد درآمد", fmt(sym.data.revenue_growth, true)], ["رشد سود", fmt(sym.data.net_profit_growth, true)], ["تعداد گزارش", String(sym.data.total_reports || 0)]].map(([l, v]) => (
                      <div key={l} className="bg-surface-900/50 rounded-lg p-3">
                        <div className="text-xs text-surface-400">{l}</div>
                        <div className="text-sm font-medium text-white mt-1">{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}