"use client";

/**
 * 📈 StockIntelligencePanel — پنل نهادی ۹‌تبه سهم (بخش ۵).
 *
 * تب‌ها: تابلو ۳۶۰ | تکنیکال | صنعت | شناسنامه | کدال | اخبار | تاریخچه | ریزمعاملات | نبض بازار
 * + کارت سیگنال کوانت (ورود/حد ضرر/تارگت‌ها/R-R).
 * هر تب مستقل با Skeleton لود می‌شود؛ داده از /stocks/v2 (Read-Through).
 */

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="h-64 bg-surface-800/30 animate-pulse rounded-xl" />,
});
const BarChartCard = dynamic(() => import("@/components/charts/BarChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});

// ── Types ───────────────────────────────────────────────────────────────────

type Freshness = "live" | "stale" | string;

interface TapeData {
  symbol: string;
  last_price: number | null;
  close_price: number | null;
  yesterday_price: number | null;
  price_min: number | null;
  price_max: number | null;
  close_change_pct: number | null;
  trade_volume: number | null;
  trade_value: number | null;
  base_volume: number | null;
  buy_real_volume: number | null;
  sell_real_volume: number | null;
  freshness?: Freshness;
}

interface TapeMatrix {
  buyer_power_ratio: number | null;
  percapita_buy_mnt: number | null;
  percapita_sell_mnt: number | null;
  smart_money: string | null;
  close_manipulation: { spread_pct: number; kind: string } | null;
  base_volume: { ratio: number; state: string } | null;
  unusual_volume: { ratio: number; level: string } | null;
  order_book_imbalance: number | null;
  tape_score: number;
}

interface Indicators {
  ok?: boolean;
  rsi_14?: number | null;
  rsi_divergence?: string | null;
  macd_cross?: string | null;
  ema_cross?: string | null;
  ema_20?: number | null;
  ema_50?: number | null;
  ema_200?: number | null;
  squeeze?: string | null;
  ichimoku?: { state?: string; tk_cross?: string; kumo_twist?: string };
  atr_14?: number | null;
  mfi_14?: number | null;
  trend_alignment_score?: number | null;
  pivots?: { classic?: Record<string, number>; camarilla?: Record<string, number> };
  source?: string;
}

interface SignalData {
  action: string;
  composite_score: number;
  layer_scores: Record<string, number>;
  entry: [number | null, number | null];
  stop_loss: number | null;
  targets: (number | null)[];
  risk_reward: number | null;
  position_size_pct: number | null;
  market_regime: string;
  reasons_pro: string[];
  reasons_con: string[];
  rr_filtered?: boolean;
}

interface Peer {
  symbol: string;
  name: string;
  close_price: number | null;
  change_pct: number | null;
  trade_value: number | null;
  pe_ttm?: number | null;
  buyer_power: number | null;
}

interface Dossier {
  identity?: Record<string, unknown>;
  major_shareholders: { name: string; percent: number | null; change: number | null }[];
  monthly_sales: { period: string; amount: number }[];
}

interface CodalData {
  announcements: { title: string; date: string | null; letter_id: string | null }[];
  monthly_sales: Record<string, unknown>[];
}

interface NewsItem {
  title: string;
  source: string | null;
  published_at: string | null;
  sentiment: string | null;
  sentiment_score: number | null;
}

interface HistoryResp {
  candles: { date: string; close: number; volume: number }[];
}

interface VolumeProfileResp {
  available: boolean;
  poc_price?: number;
  profile?: { price_low: number; price_high: number; volume: number }[];
}

interface Pulse {
  macro?: Record<string, unknown> | null;
  indices: { name: string; value: number }[];
  industry_heatmap: { industry: string; value: number; avg_change_pct: number | null }[];
}

// ── Helpers ─────────────────────────────────────────────────────────────────

const ACTION_META: Record<string, { label: string; cls: string }> = {
  strong_buy: { label: "خرید تهاجمی", cls: "bg-accent-emerald/20 text-accent-emerald" },
  accumulate: { label: "خرید پله‌ای", cls: "bg-accent-emerald/10 text-accent-emerald" },
  hold: { label: "نگهداری", cls: "bg-surface-600/25 text-surface-300" },
  reduce: { label: "کاهش حجم", cls: "bg-accent-amber/15 text-accent-amber" },
  sell: { label: "فروش/خروج", cls: "bg-accent-rose/20 text-accent-rose" },
};

const REGIME_LABELS: Record<string, string> = {
  high_volume: "بازار پرحجم",
  eroding: "بازار فرسایشی",
  falling: "بازار ریزشی",
};

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + "M";
  return v.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

const TABS = [
  { id: "tape", label: "تابلو ۳۶۰" },
  { id: "technical", label: "تکنیکال" },
  { id: "peers", label: "صنعت" },
  { id: "dossier", label: "شناسنامه" },
  { id: "codal", label: "کدال" },
  { id: "news", label: "اخبار" },
  { id: "history", label: "تاریخچه" },
  { id: "ticks", label: "ریزمعاملات" },
  { id: "pulse", label: "نبض بازار" },
] as const;

type TabId = (typeof TABS)[number]["id"];

// ── Main ────────────────────────────────────────────────────────────────────

export default function StockIntelligencePanel({ symbol }: { symbol: string }) {
  const [activeTab, setActiveTab] = useState<TabId>("tape");

  // ── تب ۱: Tape + کارت سیگنال (همیشه فعال) ──
  const { data: tapeData, isLoading: tapeLoading } = useQuery({
    queryKey: ["stocks-v2-tape", symbol],
    queryFn: async () => {
      try {
        const res = await apiGet<{ data: { tape: TapeData; matrix: TapeMatrix } }>(
          `/stocks/v2/${encodeURIComponent(symbol)}/tape`
        );
        return res?.data ?? null;
      } catch {
        return null;
      }
    },
    refetchInterval: 5_000,
    staleTime: 2_000,
  });

  const { data: signal } = useQuery({
    queryKey: ["stocks-v2-signal", symbol],
    queryFn: async () => {
      try {
        const res = await apiGet<{ data: SignalData }>(`/stocks/v2/${encodeURIComponent(symbol)}/signal`);
        return res?.data ?? null;
      } catch {
        return null;
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ── تب‌های دیگر (فقط فعال) ──
  const { data: indicators } = useQuery({
    queryKey: ["stocks-v2-indicators", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: Indicators }>(`/stocks/v2/${encodeURIComponent(symbol)}/indicators`);
      return res?.data ?? null;
    },
    enabled: activeTab === "technical",
    staleTime: 600_000,
  });

  const { data: peers } = useQuery({
    queryKey: ["stocks-v2-peers", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: { industry: string | null; peers: Peer[] } }>(
        `/stocks/v2/${encodeURIComponent(symbol)}/peers`
      );
      return res?.data ?? null;
    },
    enabled: activeTab === "peers",
    staleTime: 60_000,
  });

  const { data: dossier } = useQuery({
    queryKey: ["stocks-v2-dossier", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: Dossier }>(`/stocks/v2/${encodeURIComponent(symbol)}/dossier`);
      return res?.data ?? null;
    },
    enabled: activeTab === "dossier",
    staleTime: 300_000,
  });

  const { data: codal } = useQuery({
    queryKey: ["stocks-v2-codal", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: CodalData }>(`/stocks/v2/${encodeURIComponent(symbol)}/codal`);
      return res?.data ?? null;
    },
    enabled: activeTab === "codal",
    staleTime: 300_000,
  });

  const { data: news } = useQuery({
    queryKey: ["stocks-v2-news", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: { news: NewsItem[] } }>(`/stocks/v2/${encodeURIComponent(symbol)}/news`);
      return res?.data ?? null;
    },
    enabled: activeTab === "news",
    staleTime: 120_000,
  });

  const { data: history } = useQuery({
    queryKey: ["stocks-v2-history", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: HistoryResp }>(
        `/stocks/v2/${encodeURIComponent(symbol)}/history?limit=120`
      );
      return res?.data ?? null;
    },
    enabled: activeTab === "history",
    staleTime: 300_000,
  });

  const { data: volProfile } = useQuery({
    queryKey: ["stocks-v2-volprofile", symbol],
    queryFn: async () => {
      const res = await apiGet<{ data: VolumeProfileResp }>(
        `/stocks/v2/${encodeURIComponent(symbol)}/volume-profile`
      );
      return res?.data ?? null;
    },
    enabled: activeTab === "ticks",
    refetchInterval: 15_000,
  });

  const { data: pulse } = useQuery({
    queryKey: ["stocks-v2-pulse"],
    queryFn: async () => {
      const res = await apiGet<{ data: Pulse }>("/stocks/v2/market-pulse");
      return res?.data ?? null;
    },
    enabled: activeTab === "pulse",
    staleTime: 30_000,
  });

  const chartData = useMemo(
    () =>
      (history?.candles ?? []).map((c) => ({
        date: c.date,
        value: Number(c.close),
      })),
    [history]
  );

  const tape = tapeData?.tape;
  const matrix = tapeData?.matrix;
  const actionMeta = signal ? ACTION_META[signal.action] ?? ACTION_META.hold : null;

  return (
    <Card
      title={`🧠 هوش نهادی — ${symbol}`}
      actions={
        tape && (
          <span className="text-xs font-mono font-bold text-surface-200" dir="ltr">
            {fmt(tape.last_price)}
            <span className={`ms-2 ${(tape.close_change_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
              {fmtPct(tape.close_change_pct)}
            </span>
          </span>
        )
      }
    >
      {/* ── کارت سیگنال (همیشه بالای تب‌ها) ── */}
      {signal && actionMeta && (
        <div className="mb-4 rounded-xl border border-primary-500/30 bg-primary-600/[0.06] p-4">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <span className={`text-sm font-black px-3 py-1 rounded-lg ${actionMeta.cls}`}>
              {actionMeta.label}
            </span>
            <span className="text-xs text-surface-400">
              امتیاز: <b className="text-surface-100 font-mono">{signal.composite_score}</b>/۱۰۰
            </span>
            <span className="text-[10px] text-surface-500">رژیم: {REGIME_LABELS[signal.market_regime] ?? signal.market_regime}</span>
            {signal.risk_reward !== null && (
              <span className="text-[10px] text-surface-500">R/R: <b className="text-surface-300">{signal.risk_reward}</b></span>
            )}
            {signal.position_size_pct !== null && (
              <span className="text-[10px] text-surface-500">
                حجم پیشنهادی: <b className="text-surface-300">{signal.position_size_pct}٪</b> پرتفوی
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-[10px]">
            <MiniCell label="ورود" value={`${fmt(signal.entry[0])} – ${fmt(signal.entry[1])}`} />
            <MiniCell label="حد ضرر" value={fmt(signal.stop_loss)} tone="neg" />
            <MiniCell label="هدف ۱" value={fmt(signal.targets[0])} tone="pos" />
            <MiniCell label="هدف ۲" value={fmt(signal.targets[1])} tone="pos" />
            <MiniCell label="هدف ۳" value={fmt(signal.targets[2])} tone="pos" />
          </div>
          {(signal.reasons_pro.length > 0 || signal.reasons_con.length > 0) && (
            <div className="grid md:grid-cols-2 gap-2 mt-3 text-[10px]">
              <div className="bg-surface-800/40 rounded-lg p-2">
                <p className="text-accent-emerald font-bold mb-1">دلایل مثبت</p>
                {signal.reasons_pro.map((r, i) => <p key={i} className="text-surface-400">• {r}</p>)}
              </div>
              <div className="bg-surface-800/40 rounded-lg p-2">
                <p className="text-accent-rose font-bold mb-1">ریسک‌ها</p>
                {signal.reasons_con.map((r, i) => <p key={i} className="text-surface-400">• {r}</p>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="flex gap-1 flex-wrap border-b border-surface-700 pb-2 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === t.id
                ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                : "text-surface-400 hover:text-surface-200 hover:bg-surface-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══ تب ۱: Tape ۳۶۰ ═══ */}
      {activeTab === "tape" && (
        <div>
          {tapeLoading && <Skeleton className="h-32 w-full rounded-xl" />}
          {!tapeLoading && tape && matrix && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatBox label="قدرت خریدار" value={matrix.buyer_power_ratio?.toFixed(2) ?? "—"} tone={(matrix.buyer_power_ratio ?? 1) >= 1 ? "pos" : "neg"} />
                <StatBox label="سرانه خرید (م.ت)" value={matrix.percapita_buy_mnt?.toFixed(1) ?? "—"} />
                <StatBox
                  label="پول هوشمند"
                  value={matrix.smart_money === "inflow" ? "ورود" : matrix.smart_money === "outflow" ? "خروج" : "خنثی"}
                  tone={matrix.smart_money === "inflow" ? "pos" : matrix.smart_money === "outflow" ? "neg" : "default"}
                />
                <StatBox label="امتیاز تابلو" value={String(matrix.tape_score)} tone="accent" />
                <StatBox
                  label="حجم مبنا"
                  value={matrix.base_volume ? `${(matrix.base_volume.ratio * 100).toFixed(0)}٪` : "—"}
                  sub={matrix.base_volume?.state}
                />
                <StatBox
                  label="حجم مشکوک"
                  value={matrix.unusual_volume ? `${matrix.unusual_volume.ratio}×` : "—"}
                  sub={matrix.unusual_volume?.level}
                />
                <StatBox label="OBI (۵ مظنه)" value={matrix.order_book_imbalance?.toFixed(2) ?? "—"} />
                <StatBox
                  label="رنج‌کشی پایانی"
                  value={matrix.close_manipulation ? `${matrix.close_manipulation.spread_pct}%` : "—"}
                  sub={matrix.close_manipulation?.kind}
                />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px]">
                <MiniCell label="کمترین/بیشترین" value={`${fmt(tape.price_min)} – ${fmt(tape.price_max)}`} />
                <MiniCell label="حجم" value={fmt(tape.trade_volume)} />
                <MiniCell label="ارزش معاملات" value={fmt(tape.trade_value)} />
                <MiniCell
                  label="حقیقی (خرید/فروش)"
                  value={`${fmt(tape.buy_real_volume)} / ${fmt(tape.sell_real_volume)}`}
                  tone={(tape.buy_real_volume ?? 0) >= (tape.sell_real_volume ?? 0) ? "pos" : "neg"}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ تب ۲: تکنیکال ═══ */}
      {activeTab === "technical" && (
        <div>
          {!indicators && <Skeleton className="h-40 w-full rounded-xl" />}
          {indicators && !indicators.ok && (
            <p className="text-xs text-surface-500 py-8 text-center">داده کافی برای محاسبه اندیکاتورها موجود نیست.</p>
          )}
          {indicators?.ok && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatBox label="RSI (۱۴)" value={indicators.rsi_14?.toFixed(1) ?? "—"} sub={indicators.rsi_divergence} />
              <StatBox label="MACD" value={indicators.macd_cross ?? "—"} tone={indicators.macd_cross === "bullish_cross" ? "pos" : indicators.macd_cross === "bearish_cross" ? "neg" : "default"} />
              <StatBox
                label="ایچیموکو"
                value={
                  indicators.ichimoku?.state === "above_kumo" ? "بالای ابر" : indicators.ichimoku?.state === "below_kumo" ? "زیر ابر" : "داخل ابر"
                }
                tone={indicators.ichimoku?.state === "above_kumo" ? "pos" : indicators.ichimoku?.state === "below_kumo" ? "neg" : "default"}
              />
              <StatBox label="Squeeze" value={indicators.squeeze === "squeeze" ? "فشردگی!" : "عادی"} tone={indicators.squeeze === "squeeze" ? "accent" : "default"} />
              <StatBox label="EMA Cross" value={indicators.ema_cross === "golden" ? "طلایی" : indicators.ema_cross === "death" ? "مرگ" : "—"} tone={indicators.ema_cross === "golden" ? "pos" : indicators.ema_cross === "death" ? "neg" : "default"} />
              <StatBox label="ATR (۱۴)" value={fmt(indicators.atr_14)} />
              <StatBox label="MFI (۱۴)" value={indicators.mfi_14?.toFixed(0) ?? "—"} />
              <StatBox label="همگرایی MTF" value={indicators.trend_alignment_score?.toFixed(0) ?? "—"} />
            </div>
          )}
        </div>
      )}

      {/* ═══ تب ۳: صنعت ═══ */}
      {activeTab === "peers" && (
        <div>
          {!peers && <Skeleton className="h-40 w-full rounded-xl" />}
          {peers && (
            <>
              <p className="text-xs text-surface-500 mb-2">صنعت: {peers.industry ?? "نامشخص"} — {peers.peers.length} هم‌گروه</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="text-right py-2 px-2">نماد</th>
                      <th className="text-right py-2 px-2">قیمت</th>
                      <th className="text-right py-2 px-2">تغییر</th>
                      <th className="text-right py-2 px-2">ارزش معاملات</th>
                      <th className="text-right py-2 px-2">قدرت خریدار</th>
                    </tr>
                  </thead>
                  <tbody>
                    {peers.peers.map((p) => (
                      <tr key={p.symbol} className={`border-b border-surface-800/50 ${p.symbol === symbol ? "bg-primary-600/10" : ""}`}>
                        <td className="py-2 px-2 font-bold text-surface-200">{p.symbol}</td>
                        <td className="py-2 px-2 font-mono">{fmt(p.close_price)}</td>
                        <td className={`py-2 px-2 font-mono ${(p.change_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>{fmtPct(p.change_pct)}</td>
                        <td className="py-2 px-2 font-mono">{fmt(p.trade_value)}</td>
                        <td className="py-2 px-2 font-mono">{p.buyer_power?.toFixed(2) ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══ تب ۴: شناسنامه ═══ */}
      {activeTab === "dossier" && (
        <div>
          {!dossier && <Skeleton className="h-40 w-full rounded-xl" />}
          {dossier && (
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-bold text-surface-300 mb-2">سهامداران عمده</p>
                {dossier.major_shareholders.map((s, i) => (
                  <div key={i} className="flex items-center justify-between bg-surface-800/40 rounded-lg px-3 py-1.5 mb-1 text-[11px]">
                    <span className="text-surface-300">{s.name}</span>
                    <span className="font-mono text-surface-400">{s.percent?.toFixed(1) ?? "—"}٪</span>
                  </div>
                ))}
              </div>
              <div>
                <p className="text-xs font-bold text-surface-300 mb-2">فروش ماهانه (۱۲ دوره)</p>
                {dossier.monthly_sales.map((m) => (
                  <div key={m.period} className="flex items-center justify-between bg-surface-800/40 rounded-lg px-3 py-1.5 mb-1 text-[11px]">
                    <span className="text-surface-400" dir="ltr">{m.period}</span>
                    <span className="font-mono text-surface-300">{fmt(m.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ تب ۵: کدال ═══ */}
      {activeTab === "codal" && (
        <div>
          {!codal && <Skeleton className="h-40 w-full rounded-xl" />}
          {codal && (
            <div className="space-y-1.5">
              {codal.announcements.map((a, i) => (
                <div key={i} className="bg-surface-800/40 rounded-lg px-3 py-2 text-[11px] flex justify-between gap-2">
                  <span className="text-surface-300 truncate">{a.title}</span>
                  <span className="text-surface-600 shrink-0" dir="ltr">{a.date}</span>
                </div>
              ))}
              {codal.announcements.length === 0 && (
                <p className="text-xs text-surface-500 py-6 text-center">اطلاعیه‌ای ثبت نشده است.</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ═══ تب ۶: اخبار ═══ */}
      {activeTab === "news" && (
        <div>
          {!news && <Skeleton className="h-40 w-full rounded-xl" />}
          {news && (
            <div className="space-y-1.5">
              {news.news.map((n, i) => (
                <div key={i} className="bg-surface-800/40 rounded-lg px-3 py-2 text-[11px] flex items-center gap-2">
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      n.sentiment === "positive" ? "bg-accent-emerald" : n.sentiment === "negative" ? "bg-accent-rose" : "bg-surface-500"
                    }`}
                  />
                  <span className="text-surface-300 flex-1 truncate">{n.title}</span>
                  <span className="text-surface-600 shrink-0">{n.source}</span>
                </div>
              ))}
              {news.news.length === 0 && <p className="text-xs text-surface-500 py-6 text-center">خبری ثبت نشده است.</p>}
            </div>
          )}
        </div>
      )}

      {/* ═══ تب ۷: تاریخچه ═══ */}
      {activeTab === "history" && (
        <div>
          {!history && <Skeleton className="h-64 w-full rounded-xl" />}
          {history && chartData.length > 1 && (
            <>
              <AreaChartCard
                title="روند قیمت پایانی (۱۲۰ روز)"
                data={chartData}
                height={260}
                strokeColor="#38bdf8"
                gradientId="stockHistGrad"
                primaryLabel="قیمت"
              />
              <div className="mt-2 text-center">
                <a
                  href={`/api/v1/stocks/v2/${encodeURIComponent(symbol)}/history/export.csv`}
                  className="text-[11px] text-primary-300 hover:underline"
                  download
                >
                  ⬇ خروجی CSV
                </a>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══ تب ۸: ریزمعاملات / پروفایل حجم ═══ */}
      {activeTab === "ticks" && (
        <div>
          {!volProfile && <Skeleton className="h-56 w-full rounded-xl" />}
          {volProfile && !volProfile.available && (
            <p className="text-xs text-surface-500 py-8 text-center">ریزمعاملات امروز هنوز ثبت نشده است.</p>
          )}
          {volProfile?.available && volProfile.profile && (
            <>
              <p className="text-xs text-surface-500 mb-2">
                نقطه کنترل (POC): <b className="text-primary-300 font-mono">{fmt(volProfile.poc_price)}</b>
              </p>
              <BarChartCard
                title="پروفایل حجم بر حسب قیمت"
                data={volProfile.profile.map((p) => ({ date: fmt(p.price_low), value: p.volume }))}
                height={240}
                valueLabel="حجم"
              />
            </>
          )}
        </div>
      )}

      {/* ═══ تب ۹: نبض بازار ═══ */}
      {activeTab === "pulse" && (
        <div>
          {!pulse && <Skeleton className="h-40 w-full rounded-xl" />}
          {pulse && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {pulse.indices.map((idx) => (
                  <StatBox key={idx.name} label={idx.name} value={fmt(idx.value)} />
                ))}
              </div>
              <BarChartCard
                title="ورود/خروج پول صنایع"
                data={pulse.industry_heatmap.map((h) => ({ date: h.industry, value: h.avg_change_pct ?? 0 }))}
                height={220}
                valueLabel="تغییر ٪"
              />
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ── Small components ────────────────────────────────────────────────────────

function StatBox({ label, value, sub, tone = "default" }: { label: string; value: string; sub?: string | null; tone?: "default" | "pos" | "neg" | "accent" }) {
  const toneClass =
    tone === "pos" ? "text-accent-emerald" : tone === "neg" ? "text-accent-rose" : tone === "accent" ? "text-primary-300" : "text-surface-100";
  return (
    <div className="glass-card p-3">
      <p className="text-[10px] text-surface-500 mb-1">{label}</p>
      <p className={`font-mono text-sm font-bold ${toneClass}`} dir="ltr" style={{ textAlign: "right" }}>
        {value}
      </p>
      {sub && <p className="text-[9px] mt-0.5 text-surface-600">{sub}</p>}
    </div>
  );
}

function MiniCell({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "pos" | "neg" }) {
  const toneClass = tone === "pos" ? "text-accent-emerald" : tone === "neg" ? "text-accent-rose" : "text-surface-200";
  return (
    <div className="bg-surface-800/40 rounded-lg px-2.5 py-1.5">
      <p className="text-[9px] text-surface-500">{label}</p>
      <p className={`font-mono text-[11px] font-bold ${toneClass}`} dir="ltr">{value}</p>
    </div>
  );
}
