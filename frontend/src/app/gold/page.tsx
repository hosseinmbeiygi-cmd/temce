"use client";

import { useQuery } from "@tanstack/react-query";
import { getSnapshot, getSnapshotHistory, planDCA, priceOption, protectiveCollar } from "@/lib/goldApi";
import { subscribeGoldWS } from "@/lib/goldApi";
import { useState, useEffect } from "react";
import type { Snapshot, AssetBlock, FundBlock } from "@/types/gold";
import AddAlertButton from "@/components/AddAlertButton";

// ── Helpers ──────────────────────────────────────────────────────

function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return n.toLocaleString("fa-IR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return sign + n.toFixed(digits) + "٪";
}

function bubbleColor(pct: number | null): { bg: string; text: string; label: string; ring: string } {
  if (pct === null) return { bg: "bg-zinc-800/40", text: "text-zinc-500", label: "—", ring: "ring-zinc-700" };
  if (pct < 5) return { bg: "bg-emerald-500/10", text: "text-emerald-300", label: "بدون حباب", ring: "ring-emerald-700/30" };
  if (pct < 12) return { bg: "bg-lime-500/10", text: "text-lime-300", label: "حباب کم", ring: "ring-lime-700/30" };
  if (pct < 22) return { bg: "bg-amber-500/10", text: "text-amber-300", label: "حباب متوسط", ring: "ring-amber-700/30" };
  return { bg: "bg-rose-500/10", text: "text-rose-300", label: "حباب شدید", ring: "ring-rose-700/30" };
}

function decisionStyle(decision: string): { bg: string; text: string; ring: string; label: string } {
  if (decision === "GREEN") return { bg: "from-emerald-500/20 to-emerald-600/5", text: "text-emerald-300", ring: "ring-emerald-500/40", label: "سبز — ورود" };
  if (decision === "YELLOW") return { bg: "from-amber-500/20 to-amber-600/5", text: "text-amber-300", ring: "ring-amber-500/40", label: "زرد — احتیاط" };
  return { bg: "from-rose-500/20 to-rose-600/5", text: "text-rose-300", ring: "ring-rose-500/40", label: "قرمز — صبر" };
}

// ── Sub-components ──────────────────────────────────────────────

function Hero({ snap }: { snap: Snapshot }) {
  const ds = decisionStyle(snap.score.decision);
  const refs = snap.references;
  const [prevScore, setPrevScore] = useState(snap.score.total);
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    if (snap.score.total !== prevScore) {
      setPulse(true);
      setPrevScore(snap.score.total);
      const t = setTimeout(() => setPulse(false), 1200);
      return () => clearTimeout(t);
    }
  }, [snap.score.total, prevScore]);

  return (
    <section
      className={`relative overflow-hidden rounded-2xl ring-1 ${ds.ring} bg-gradient-to-br ${ds.bg} backdrop-blur p-8 transition-all duration-700`}
      style={{
        animation: pulse ? "scorePulse 1.2s ease-out" : undefined,
      }}
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Score */}
        <div className="lg:col-span-4 text-center lg:text-right">
          <div className="text-xs text-zinc-400 mb-1">امتیاز تصمیم‌گیری</div>
          <div className="flex items-baseline justify-center lg:justify-start gap-2">
            <span
              className={`text-6xl md:text-7xl font-black ${ds.text} tabular-nums transition-all duration-500 gold-hero-score`}
              key={snap.score.total}
            >
              {snap.score.total}
            </span>
            <span className="text-zinc-500 text-sm">/ ۱۰۰</span>
          </div>
          <div
            className={`mt-2 inline-block px-3 py-1 rounded-full text-sm font-semibold ${ds.text} bg-zinc-900/60 ring-1 ring-current/30 transition-all duration-500`}
            key={snap.score.decision}
          >
            {ds.label}
          </div>
          {snap.score.hard_stop_active && (
            <div className="mt-3 text-xs text-rose-300 bg-rose-950/50 ring-1 ring-rose-700/40 rounded p-2">
              ⚠️ {snap.score.hard_stop_reason}
            </div>
          )}
        </div>

        {/* Refs */}
        <div className="lg:col-span-5 grid grid-cols-3 gap-3">
          <RefTile label="اونس جهانی" value={fmt(refs.xau_usd, 0)} unit="$" />
          <RefTile label="دلار آزاد" value={fmt(refs.usd_irt, 0)} unit="تومان" />
          <RefTile
            label="شکاف درهم"
            value={fmt(refs.aed_gap_pct, 2)}
            unit="٪"
            tone={Math.abs(refs.aed_gap_pct) < 1 ? "good" : Math.abs(refs.aed_gap_pct) < 3 ? "warn" : "bad"}
          />
        </div>

        {/* Score components */}
        <div className="lg:col-span-3 space-y-1.5">
          <div className="text-xs text-zinc-400 mb-2">اجزا</div>
          <CompRow label="حباب" value={snap.score.components.bubble} max={20} />
          <CompRow label="NAV" value={snap.score.components.nav} max={18} />
          <CompRow label="TSETMC" value={snap.score.components.tsetmc} max={18} />
          <CompRow label="تکنیکال" value={snap.score.components.technical} max={15} />
          <CompRow label="پریتی" value={snap.score.components.parity} max={15} />
          <CompRow label="NAV 7d" value={snap.score.components.fund_flow} max={14} />
        </div>
      </div>
    </section>
  );
}

function RefTile({ label, value, unit, tone = "neutral" }: { label: string; value: string; unit?: string; tone?: "good" | "warn" | "bad" | "neutral" }) {
  const toneClass = { good: "text-emerald-300", warn: "text-amber-300", bad: "text-rose-300", neutral: "text-zinc-100" }[tone];
  return (
    <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-3">
      <div className="text-[10px] text-zinc-500 mb-1">{label}</div>
      <div className={`text-lg font-bold tabular-nums ${toneClass}`}>
        {value}
        {unit && <span className="text-[10px] text-zinc-500 mr-1">{unit}</span>}
      </div>
    </div>
  );
}

function CompRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = (value / max) * 100;
  const color = pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-14 text-zinc-400">{label}</div>
      <div className="flex-1 h-1.5 bg-zinc-800/80 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="w-8 text-left text-zinc-300 tabular-nums">{value}</div>
    </div>
  );
}

// ── Coin card ──────────────────────────────────────────────────

function CoinCard({ a }: { k: string; a: AssetBlock }) {
  const c = bubbleColor(a.bubble_pct);
  return (
    <div className={`rounded-xl ring-1 ${c.ring} ${c.bg} p-4 backdrop-blur transition hover:scale-[1.01]`}>
      <div className="flex items-start justify-between mb-2">
        <div className="text-sm font-semibold text-zinc-100">{a.display_name}</div>
        <div className="flex items-center gap-1.5">
          <AddAlertButton compact symbol={a.symbol} market="gold" entry={a.market_price} />
          <div className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ring-current/20 ${c.text}`}>{c.label}</div>
        </div>
      </div>
      <div className="text-2xl font-black text-zinc-100 tabular-nums mb-1">{fmt(a.market_price)}</div>
      <div className="text-[10px] text-zinc-500 mb-3 flex justify-between">
        <span>ذاتی: {fmt(a.fair_value)}</span>
        <span>دلار ضمنی: {fmt(a.implied_usd)}</span>
      </div>
      <div className="flex items-baseline justify-between border-t border-zinc-800/60 pt-2">
        <div className="text-[10px] text-zinc-500">حباب</div>
        <div className={`text-lg font-bold tabular-nums ${c.text}`}>{fmtPct(a.bubble_pct)}</div>
      </div>
    </div>
  );
}

// ── Fund row ───────────────────────────────────────────────────

function FundRow({ f }: { f: FundBlock }) {
  const c = bubbleColor(f.bubble_pct);
  const bprTone = f.bpr >= 2 ? "text-emerald-300" : f.bpr >= 1 ? "text-amber-300" : "text-rose-300";
  return (
    <tr className="border-b border-zinc-800/40 hover:bg-zinc-800/20 transition">
      <td className="py-2.5 px-3 text-sm text-zinc-200">{f.fund_name}</td>
      <td className="py-2.5 px-3 text-xs text-zinc-400 tabular-nums">{fmt(f.nav_per_unit)}</td>
      <td className="py-2.5 px-3 text-xs text-zinc-200 tabular-nums">{fmt(f.market_price)}</td>
      <td className={`py-2.5 px-3 text-xs font-bold tabular-nums ${c.text}`}>{fmtPct(f.bubble_pct)}</td>
      <td className={`py-2.5 px-3 text-xs tabular-nums ${bprTone}`}>{f.bpr.toFixed(2)}</td>
      <td className="py-2.5 px-3 text-xs text-zinc-400 tabular-nums">{(f.net_inflow / 1e9).toFixed(1)}B</td>
      <td className="py-2.5 px-3"><AddAlertButton compact symbol={f.symbol} market="fund" entry={f.market_price} /></td>
    </tr>
  );
}

// ── Main ───────────────────────────────────────────────────────

export default function GoldUnifiedPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["gold", "snapshot"],
    queryFn: getSnapshot,
    refetchInterval: 60_000,
    staleTime: 55_000,
  });

  // WebSocket برای live update
  useEffect(() => {
    const unsub = subscribeGoldWS(() => {
      // silent refetch when WS message arrives
      refetch();
    });
    return unsub;
  }, [refetch]);

  const handleExport = () => {
    window.print();
  };

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <GoldSkeleton type="hero" />
        <GoldSkeleton type="grid" />
        <GoldSkeleton type="table" />
      </div>
    );
  }

  const coinKeys = Object.keys(data.coins);
  const goldKeys = Object.keys(data.gold);

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex items-center justify-between print:hidden">
        <div className="text-xs text-zinc-500">
          آخرین به‌روزرسانی: {new Date(data.snapshot_at).toLocaleString("fa-IR")} • منبع:{" "}
          <span className="text-zinc-300">{data.references.source}</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            className="text-xs bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 rounded-lg px-3 py-1.5 transition"
          >
            🔄 به‌روزرسانی
          </button>
          <button
            onClick={handleExport}
            className="text-xs bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 ring-1 ring-amber-500/40 rounded-lg px-3 py-1.5 transition"
          >
            📄 چاپ / PDF
          </button>
        </div>
      </div>

      {/* Hero: Score + refs + components */}
      <Hero snap={data} />

      {/* Gold & Coins */}
      <section id="coins">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-zinc-200">💰 طلا و سکه</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {coinKeys.map((k) => (
            <CoinCard key={k} k={k} a={data.coins[k]} />
          ))}
          {goldKeys.map((k) => (
            <CoinCard key={k} k={k} a={data.gold[k]} />
          ))}
        </div>
      </section>

      {/* Funds */}
      <section id="funds">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-zinc-200">🏦 صندوق‌های طلا (P/NAV)</h2>
          <span className="text-[10px] text-zinc-500">{data.funds.length} صندوق</span>
        </div>
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="text-[10px] text-zinc-500 border-b border-zinc-800/60 bg-zinc-900/60">
                <th className="text-right py-2.5 px-3 font-medium">صندوق</th>
                <th className="text-right py-2.5 px-3 font-medium">NAV</th>
                <th className="text-right py-2.5 px-3 font-medium">بازار</th>
                <th className="text-right py-2.5 px-3 font-medium">حباب NAV</th>
                <th className="text-right py-2.5 px-3 font-medium">BPR</th>
                <th className="text-right py-2.5 px-3 font-medium">جریان خالص</th>
                <th className="text-right py-2.5 px-3 font-medium">هشدار</th>
              </tr>
            </thead>
            <tbody>
              {data.funds.map((f) => <FundRow key={f.symbol} f={f} />)}
              {data.funds.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-zinc-500 text-sm">
                    داده NAV موجود نیست
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Decision rationale */}
      <section>
        <h2 className="text-base font-semibold text-zinc-200 mb-3">📊 تحلیل امتیاز</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <ReasonCard title="حباب سکه" reason={data.score.components.bubble_reason} value={data.score.components.bubble} max={20} />
          <ReasonCard title="NAV صندوق" reason={data.score.components.nav_reason} value={data.score.components.nav} max={18} />
          <ReasonCard title="قدرت خریدار" reason={data.score.components.tsetmc_reason} value={data.score.components.tsetmc} max={18} />
          <ReasonCard title="RSI اونس" reason={data.score.components.technical_reason} value={data.score.components.technical} max={15} />
          <ReasonCard title="شکاف درهم" reason={data.score.components.parity_reason} value={data.score.components.parity} max={15} />
          <ReasonCard title="NAV 7d" reason={data.score.components.fund_flow_reason} value={data.score.components.fund_flow} max={14} />
        </div>
      </section>

      {/* Quality flag */}
      {data.quality_flag !== "clean" && (
        <div className="rounded-xl ring-1 ring-amber-700/40 bg-amber-950/30 p-3 text-xs text-amber-300">
          ⚠️ منبع داده: {data.quality_flag} (fallback فعال)
        </div>
      )}

      {/* Inline sections — باقی ابزارها در همین صفحه */}
      <TechnicalSection />
      <OptionsSection />
      <DCASection score={data.score.total} />
    </div>
  );
}

// ── Technical (نمودار قیمت XAU) ─────────────────────────────────

function TechnicalSection() {
  const [days, setDays] = useState(30);
  const { data: hist } = useQuery({
    queryKey: ["gold", "history", "XAUUSD", days],
    queryFn: () => getSnapshotHistory("XAUUSD", days),
    refetchInterval: 5 * 60_000,
  });

  const points = (hist?.data?.items ?? []).map((p) => ({
    date: (p.snapshot_at || "").slice(0, 10),
    value: p.market_price,
  }));

  return (
    <section id="technical">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-zinc-200">📈 تکنیکال اونس</h2>
        <div className="flex gap-1">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`text-[10px] px-3 py-1 rounded ${
                days === d ? "bg-amber-500/20 text-amber-300" : "bg-zinc-800/60 text-zinc-400"
              }`}
            >
              {d} روز
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 p-4">
        {points.length > 1 ? <PriceChart points={points} /> : <div className="text-zinc-500 text-sm text-center py-8">داده کافی نیست</div>}
      </div>
    </section>
  );
}

function PriceChart({ points }: { points: Array<{ date: string; value: number }> }) {
  if (points.length < 2) return null;
  const w = 1200, h = 220, padX = 30, padY = 20;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const x = (i: number) => padX + (i / (points.length - 1)) * (w - 2 * padX);
  const y = (v: number) => h - padY - ((v - min) / range) * (h - 2 * padY);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p.value)}`).join(" ");
  const area = `${path} L ${x(points.length - 1)} ${h - padY} L ${x(0)} ${h - padY} Z`;
  const current = points[points.length - 1].value;
  const first = points[0].value;
  const changePct = ((current - first) / first) * 100;
  const trendColor = changePct > 0 ? "text-emerald-300" : "text-rose-300";
  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <div>
          <div className="text-2xl font-bold text-zinc-100 tabular-nums">${fmt(current, 2)}</div>
          <div className={`text-xs ${trendColor}`}>
            {changePct > 0 ? "▲" : "▼"} {fmt(Math.abs(changePct), 2)}٪
          </div>
        </div>
        <div className="text-[10px] text-zinc-500">{points[0].date} → {points[points.length - 1].date}</div>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="gold-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#gold-grad)" />
        <path d={path} fill="none" stroke="#f59e0b" strokeWidth="2" />
      </svg>
    </div>
  );
}

// ── Options (Black-76 خلاصه) ────────────────────────────────────

function OptionsSection() {
  const [expiry, setExpiry] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() + 1);
    return d.toISOString().slice(0, 10);
  });
  // F ≈ NAV صندوق عیار
  const forward = 3500;
  const { data: opt } = useQuery({
    queryKey: ["gold", "opt", forward, expiry],
    queryFn: () => priceOption({ forward, strike: forward, expiry, iv: 0.25 }),
  });
  const { data: collar } = useQuery({
    queryKey: ["gold", "collar", forward, expiry],
    queryFn: () => protectiveCollar({ spot: forward, put_strike: forward * 0.95, call_strike: forward * 1.05, expiry, iv: 0.25 }),
  });

  return (
    <section id="options">
      <h2 className="text-base font-semibold text-zinc-200 mb-3">🎯 اختیار معامله (Black-76)</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm text-zinc-300">ATM Option (عیار، F={forward})</div>
            <input
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className="bg-zinc-800/60 border border-zinc-700/60 rounded text-xs px-2 py-1 text-zinc-300"
            />
          </div>
          {opt ? (
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
                <div className="text-[10px] text-zinc-500">Call</div>
                <div className="text-xl font-bold text-emerald-300 tabular-nums">{fmt(opt.call, 2)}</div>
              </div>
              <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
                <div className="text-[10px] text-zinc-500">Put</div>
                <div className="text-xl font-bold text-rose-300 tabular-nums">{fmt(opt.put, 2)}</div>
              </div>
            </div>
          ) : (
            <div className="text-zinc-500 text-xs text-center py-4">در حال محاسبه...</div>
          )}
        </div>

        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 p-4">
          <div className="text-sm text-zinc-300 mb-2">Protective Collar (±۵٪)</div>
          {collar ? (
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
                <div className="text-[10px] text-zinc-500">کف</div>
                <div className="text-lg font-bold text-emerald-300 tabular-nums">{fmt(collar.floor, 0)}</div>
              </div>
              <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
                <div className="text-[10px] text-zinc-500">هزینه</div>
                <div className={`text-lg font-bold tabular-nums ${collar.cost > 0 ? "text-rose-300" : "text-emerald-300"}`}>
                  {fmt(collar.cost, 2)}
                </div>
              </div>
              <div className="bg-zinc-800/40 rounded-lg p-3 text-center">
                <div className="text-[10px] text-zinc-500">سقف</div>
                <div className="text-lg font-bold text-rose-300 tabular-nums">{fmt(collar.cap, 0)}</div>
              </div>
            </div>
          ) : (
            <div className="text-zinc-500 text-xs text-center py-4">در حال محاسبه...</div>
          )}
        </div>
      </div>
    </section>
  );
}

// ── DCA inline calculator ───────────────────────────────────────

function DCASection({ score }: { score: number }) {
  const [capital, setCapital] = useState(100_000_000);
  const [risk, setRisk] = useState<"balanced" | "conservative" | "aggressive">("balanced");
  const [vehicle, setVehicle] = useState<"" | "etf" | "cert" | "melted" | "coin">("");

  const { data: plan } = useQuery({
    queryKey: ["gold", "dca", capital, risk, score, vehicle],
    queryFn: () =>
      planDCA({
        total_capital_irt: capital,
        risk_profile: risk,
        current_score: score,
        preferred_vehicle: (vehicle || undefined) as "etf" | "cert" | "melted" | "coin" | undefined,
      }),
  });

  return (
    <section id="dca">
      <h2 className="text-base font-semibold text-zinc-200 mb-3">💼 پلن DCA (محاسبه‌گر)</h2>
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <input
            type="number"
            value={capital}
            onChange={(e) => setCapital(parseInt(e.target.value) || 0)}
            placeholder="سرمایه (تومان)"
            className="bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100"
          />
          <select
            value={risk}
            onChange={(e) => setRisk(e.target.value as "balanced" | "conservative" | "aggressive")}
            className="bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100"
          >
            <option value="conservative">محافظه‌کار (۲۰/۴۰/۴۰)</option>
            <option value="balanced">متعادل (۳۰/۴۰/۳۰)</option>
            <option value="aggressive">تهاجمی (۵۰/۳۰/۲۰)</option>
          </select>
          <select
            value={vehicle}
            onChange={(e) => setVehicle(e.target.value as "" | "etf" | "cert" | "melted" | "coin")}
            className="bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100"
          >
            <option value="">— ابزار خودکار —</option>
            <option value="etf">صندوق ETF</option>
            <option value="cert">گواهی شمش</option>
            <option value="melted">طلای آب‌شده</option>
            <option value="coin">سکه فیزیکی</option>
          </select>
          <div className="bg-zinc-800/40 rounded-lg px-3 py-2 text-sm text-zinc-300 text-center">
            امتیاز فعلی: <span className="font-bold text-amber-300">{score}</span>
          </div>
        </div>

        {plan && (
          <div className="space-y-2">
            <div className="grid grid-cols-3 gap-2 text-xs">
              <Stat label="ابزار" value={plan.recommended_vehicle} />
              <Stat label="کارمزد" value={fmt(plan.total_fee_irt) + " ت"} />
              <Stat label="Stop/TP" value={`-${plan.stop_loss_pct}٪ / +${plan.take_profit_pct}٪`} />
            </div>
            <div className="space-y-1.5">
              {plan.ladder.map((t) => (
                <div key={t.tranche} className="flex items-center gap-2 bg-zinc-800/40 rounded-lg p-2">
                  <div className="text-[10px] text-zinc-500 w-8">پله {t.tranche}</div>
                  <div className="flex-1 text-xs text-zinc-300 truncate">{t.trigger}</div>
                  <div className="text-xs text-zinc-100 tabular-nums">{fmt(t.amount_irt)}</div>
                  <div className="text-[10px] text-zinc-500 tabular-nums w-12 text-left">{Math.round(t.pct * 100)}٪</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-zinc-800/40 rounded-lg p-2 text-center">
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className="text-sm font-bold text-zinc-100">{value}</div>
    </div>
  );
}

// ── Skeleton Loader ────────────────────────────────────────────

function GoldSkeleton({ type }: { type: "hero" | "grid" | "table" }) {
  const pulse = "animate-pulse bg-zinc-800/60 rounded";

  if (type === "hero") {
    return (
      <div className={`${pulse} h-64 rounded-2xl`}>
        <div className="p-8 flex gap-6">
          <div className="flex-1 space-y-3">
            <div className="h-8 w-24 bg-zinc-700/60 rounded" />
            <div className="h-4 w-32 bg-zinc-700/40 rounded" />
          </div>
          <div className="flex-1 grid grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-zinc-700/40 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (type === "grid") {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className={`${pulse} h-32 rounded-xl`} />
        ))}
      </div>
    );
  }

  return (
    <div className={`${pulse} h-64 rounded-xl`}>
      <div className="p-4 space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-8 bg-zinc-700/40 rounded" />
        ))}
      </div>
    </div>
  );
}

function ReasonCard({ title, reason, value, max }: { title: string; reason: string; value: number; max: number }) {
  const pct = (value / max) * 100;
  const color = pct >= 80 ? "text-emerald-300" : pct >= 50 ? "text-amber-300" : "text-rose-300";
  return (
    <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 p-3">
      <div className="flex items-center justify-between mb-1">
        <div className="text-sm font-semibold text-zinc-200">{title}</div>
        <div className={`text-sm font-bold tabular-nums ${color}`}>
          {value}<span className="text-zinc-500 text-xs">/{max}</span>
        </div>
      </div>
      <div className="text-[11px] text-zinc-400 leading-relaxed">{reason}</div>
    </div>
  );
}
