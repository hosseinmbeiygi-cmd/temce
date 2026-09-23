"use client";

import { useQuery } from "@tanstack/react-query";
import { getSnapshot } from "@/lib/goldApi";
import { useState, useMemo } from "react";

// ── Helpers ──────────────────────────────────────────────────────
function fmt(n: number | null | undefined, d = 0): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return n.toLocaleString("fa-IR", { maximumFractionDigits: d, minimumFractionDigits: d });
}
function fmtPct(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return (n > 0 ? "+" : "") + n.toFixed(d) + "٪";
}

// ── Pure calculations — مطابق spec Python ────────────────────────
function calcNavPremium(market: number, nav: number) {
  const pct = ((market - nav) / nav) * 100;
  let signal: "BUY" | "SELL" | "NEUTRAL" = "NEUTRAL";
  let reason = "";
  if (pct > 2) { signal = "SELL"; reason = `صندوق ${pct.toFixed(2)}٪ بیش از NAV (اشباع خرید)`; }
  else if (pct < -1) { signal = "BUY"; reason = `صندوق ${Math.abs(pct).toFixed(2)}٪ زیر NAV (فرصت خرید)`; }
  else reason = `محدوده منطقی (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}٪)`;
  return { premium_pct: pct, signal, reason };
}
function calcCoinBubble(coinPrice: number, goldOzUsd: number, usdRate: number) {
  const intrinsic = goldOzUsd * (8.133 / 31.1035) * 0.915 * usdRate;
  const pct = ((coinPrice - intrinsic) / intrinsic) * 100;
  let signal: "BUY" | "SELL" | "NEUTRAL" = "NEUTRAL";
  let reason = "";
  if (pct > 5) { signal = "SELL"; reason = `سکه ${pct.toFixed(2)}٪ حباب دارد`; }
  else if (pct < -3) { signal = "BUY"; reason = `${Math.abs(pct).toFixed(2)}٪ تخفیف`; }
  else reason = `محدوده منطقی (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}٪)`;
  return { coin_intrinsic: intrinsic, bubble_pct: pct, signal, reason };
}
function calcDollarReturn(entryIrr: number, curIrr: number, entryUsd: number, curUsd: number) {
  const usdEntry = entryIrr / entryUsd;
  const usdCur = curIrr / curUsd;
  const dollarRoi = ((usdCur - usdEntry) / usdEntry) * 100;
  const irrRoi = ((curIrr - entryIrr) / entryIrr) * 100;
  const usdGrowth = ((curUsd - entryUsd) / entryUsd) * 100;
  return { irr_roi_pct: +irrRoi.toFixed(2), dollar_roi_pct: +dollarRoi.toFixed(2), usd_growth_pct: +usdGrowth.toFixed(2), is_beating: dollarRoi > 0, usdEntry, usdCur };
}
function calcArbitrage(etfPerGram: number, physPerGram: number, costPct = 0.003) {
  const gross = ((physPerGram - etfPerGram) / etfPerGram) * 100;
  const net = gross - costPct * 100;
  let action: string = "NO_ARBITRAGE";
  let strategy = "اختلاف کمتر از هزینه — آربیتراژ توجیه ندارد";
  if (net > 1.5) { action = "BUY_ETF_SELL_PHYSICAL"; strategy = "خرید ETF و فروش آب‌شده"; }
  else if (net < -1.5) { action = "BUY_PHYSICAL_SELL_ETF"; strategy = "خرید فیزیکی و فروش ETF"; }
  return { gross_spread_pct: +gross.toFixed(2), net_spread_pct: +net.toFixed(2), action, strategy };
}
class FuturesCalc {
  leverage = 10;
  imr = 0.10; mmr = 0.05;
  liq(entry: number, type: string) { const buf = this.imr - this.mmr; return type === "LONG" ? entry * (1 - buf) : entry * (1 + buf); }
  health(equity: number, posVal: number) { const used = posVal * this.imr; return used === 0 ? Infinity : equity / used; }
}
const ETF = [
  { fa: "زرافشان", sym: "ZARFSHANG", isin: "IRO1ZARA0001", liq: "high", fee: 0.5 },
  { fa: "لوتوس", sym: "LOTUS", isin: "IRO1LOTU0001", liq: "high", fee: 0.5 },
  { fa: "گوهر", sym: "GOHAR", isin: "IRO1GOHA0001", liq: "medium", fee: 0.5 },
  { fa: "ثامان", sym: "SAMAN", isin: "IRO1SAMA0001", liq: "medium", fee: 0.5 },
];
const PHYS = [
  { fa: "سکه بهار آزادی", w: "8.133g", p: "900/1000" },
  { fa: "نیم‌سکه", w: "4.066g", p: "900/1000" },
  { fa: "ربع‌سکه", w: "2.033g", p: "900/1000" },
  { fa: "گرم ۱۸ عیار", w: "1g", p: "750/1000" },
  { fa: "مثقال", w: "4.608g", p: "1000/1000" },
];

export default function AntigravityPage() {
  const { data: snap } = useQuery({ queryKey: ["gold", "snapshot"], queryFn: getSnapshot, refetchInterval: 30_000 });
  const xau = snap?.references.xau_usd ?? 2650;
  const usd = snap?.references.usd_irt ?? 85000;

  // NAV inputs
  const [navMarket, setNavMarket] = useState(36500);
  const [navNav, setNavNav] = useState(36000);
  const navRes = useMemo(() => calcNavPremium(navMarket, navNav), [navMarket, navNav]);

  // Coin bubble
  const [coinPrice, setCoinPrice] = useState(45000000);
  const bubbleRes = useMemo(() => calcCoinBubble(coinPrice, xau, usd), [coinPrice, xau, usd]);

  // Futures
  const [futEntry, setFutEntry] = useState(45000000);
  const [futType, setFutType] = useState<"LONG" | "SHORT">("LONG");
  const [futEquity, setFutEquity] = useState(150000000);
  const fut = useMemo(() => {
    const c = new FuturesCalc();
    const liq = c.liq(futEntry, futType);
    const posVal = futEntry * 10;
    const hl = c.health(futEquity, posVal);
    const dist = futType === "LONG" ? ((futEntry - liq) / futEntry) * 100 : ((liq - futEntry) / futEntry) * 100;
    let level: string = "SAFE";
    let msg = `✅ سالم — سلامت ${hl.toFixed(2)}`;
    if (hl < 1.2) { level = "CRITICAL"; msg = `⚠️ کال‌مارجین! فاصله ${dist.toFixed(2)}٪`; }
    else if (hl < 2.0) { level = "WARNING"; msg = `⚡ هشدار — سلامت ${hl.toFixed(2)}`; }
    return { liq, hl, dist, level, msg };
  }, [futEntry, futType, futEquity]);

  // Dollar-adjusted
  const [dEntryIrr, setDEntryIrr] = useState(40000000);
  const [dCurIrr, setDCurIrr] = useState(46000000);
  const [dEntryUsd, setDEntryUsd] = useState(80000);
  const [dCurUsd, setDCurUsd] = useState(85000);
  const dRes = useMemo(() => calcDollarReturn(dEntryIrr, dCurIrr, dEntryUsd, dCurUsd), [dEntryIrr, dCurIrr, dEntryUsd, dCurUsd]);

  // Arbitrage
  const [arbEtf, setArbEtf] = useState(7200000);
  const [arbPhys, setArbPhys] = useState(7400000);
  const arbRes = useMemo(() => calcArbitrage(arbEtf, arbPhys), [arbEtf, arbPhys]);

  // Kill-switch
  const [ksOunce2h, setKsOunce2h] = useState(1.2);
  const [ksUsd2h, setKsUsd2h] = useState(0.8);
  const [ksMargin, setKsMargin] = useState(false);
  const [ksFreeze, setKsFreeze] = useState(false);
  const ksStatus = useMemo(() => {
    if (Math.abs(ksOunce2h) > 5 || Math.abs(ksUsd2h) > 5 || ksMargin || ksFreeze) return "ACTIVE" as const;
    if (Math.abs(ksOunce2h) > 3 || Math.abs(ksUsd2h) > 3) return "WARNING" as const;
    return "NORMAL" as const;
  }, [ksOunce2h, ksUsd2h, ksMargin, ksFreeze]);

  // Signal generator
  const [sigEtf, setSigEtf] = useState("زرافشان");
  const [sigLev, setSigLev] = useState(1);
  const sigNav = navRes; const sigBubble = bubbleRes;
  const sigAction = useMemo(() => {
    if (ksStatus === "ACTIVE") return "CLOSE";
    if (sigNav.signal === "BUY" && sigBubble.signal !== "SELL") return "BUY";
    if (sigBubble.signal === "BUY" && sigNav.signal !== "SELL") return "BUY";
    if (sigNav.signal === "SELL" || sigBubble.signal === "SELL") {
      if (sigNav.signal === "SELL" && sigBubble.signal === "SELL") return "SELL";
      if (sigNav.signal === "BUY" || sigBubble.signal === "BUY") return "HOLD";
      return "SELL";
    }
    return "HOLD";
  }, [sigNav.signal, sigBubble.signal, ksStatus]);
  const sigConf = useMemo(() => {
    if (ksStatus === "ACTIVE") return 0.95;
    let s = 0.5;
    if (sigNav.signal === "BUY") s += 0.15; if (sigNav.signal === "SELL") s -= 0.15;
    if (sigBubble.signal === "BUY") s += 0.15; if (sigBubble.signal === "SELL") s -= 0.1;
    if (arbRes.action !== "NO_ARBITRAGE") s += 0.1;
    if (ksStatus === "WARNING") s -= 0.15;
    return Math.max(0, Math.min(1, +s.toFixed(2)));
  }, [sigNav.signal, sigBubble.signal, arbRes.action, ksStatus]);

  const chosenEtf = ETF.find(e => e.fa === sigEtf)!;
  const entryMid = navMarket;
  const sl = sigAction === "BUY" ? entryMid * 0.97 : sigAction === "SELL" ? entryMid * 1.03 : entryMid * 0.97;
  const tp1 = sigAction === "BUY" ? entryMid * 1.03 : sigAction === "SELL" ? entryMid * 0.97 : entryMid * 1.02;
  const tp2 = sigAction === "BUY" ? entryMid * 1.06 : sigAction === "SELL" ? entryMid * 0.94 : entryMid * 1.04;
  const rr = Math.abs(tp1 - entryMid) / Math.abs(entryMid - sl);

  const outputJson = {
    timestamp: new Date().toISOString(),
    asset: { symbol: chosenEtf.sym, market: "TSE", current_price: entryMid },
    signal: { action: sigAction, confidence_score: sigConf, timeframe: sigAction === "CLOSE" ? "SCALP" : sigAction === "BUY" ? "SWING" : sigAction === "SELL" ? "INTRADAY" : "SWING" },
    trade_parameters: { entry_range: [+(entryMid * 0.995).toFixed(0), +(entryMid * 1.005).toFixed(0)], stop_loss: +sl.toFixed(0), target_1: +tp1.toFixed(0), target_2: +tp2.toFixed(0), risk_reward_ratio: +rr.toFixed(2) },
    metrics: { nav_premium_pct: +sigNav.premium_pct.toFixed(2), coin_bubble_pct: +sigBubble.bubble_pct.toFixed(2), dollar_adjusted_expected_roi: dRes.dollar_roi_pct, gross_spread_pct: arbRes.gross_spread_pct, net_spread_pct: arbRes.net_spread_pct },
    leverage_and_margin: { leverage: sigLev, liquidation_price: sigLev > 1 ? +(new FuturesCalc().liq(entryMid, "LONG")).toFixed(0) : null, health_ratio: sigLev > 1 ? +fut.hl.toFixed(2) : null, risk_level: sigLev > 1 ? (fut.level === "SAFE" ? "LOW" : fut.level === "WARNING" ? "MEDIUM" : fut.level === "CRITICAL" ? "EXTREME" : "HIGH") : "LOW" },
    rationale: `NAV: ${sigNav.reason} | حباب: ${sigBubble.reason} | آربیتراژ: ${arbRes.strategy} | Kill-Switch: ${ksStatus}`,
    kill_switch_status: ksStatus,
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="rounded-2xl bg-gradient-to-br from-amber-500/10 via-zinc-900 to-zinc-900 ring-1 ring-amber-500/20 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-black text-zinc-100">🚀 Antigravity — ماژول طلا</h1>
            <p className="text-xs text-zinc-400 mt-1">KPI: بازده دلاری (Dollar-Adjusted) • Manual Decision Support • بدون اجرای خودکار</p>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="bg-zinc-800/60 ring-1 ring-zinc-700/50 rounded-lg px-3 py-1.5">اونس: <b className="text-amber-300">${fmt(xau)}</b></span>
            <span className="bg-zinc-800/60 ring-1 ring-zinc-700/50 rounded-lg px-3 py-1.5">دلار: <b className="text-emerald-300">{fmt(usd)} ت</b></span>
            <span className={`rounded-lg px-3 py-1.5 ring-1 ${ksStatus === "ACTIVE" ? "bg-rose-500/20 text-rose-300 ring-rose-500/30" : ksStatus === "WARNING" ? "bg-amber-500/20 text-amber-300 ring-amber-500/30" : "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20"}`}>Kill: {ksStatus}</span>
          </div>
        </div>
      </div>

      {/* ETF Registry */}
      <section>
        <h2 className="text-sm font-bold text-zinc-200 mb-3">📊 صندوق‌های ETF طلا</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {ETF.map(e => (
            <div key={e.sym} className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
              <div className="flex justify-between items-start mb-2">
                <div className="text-sm font-bold text-zinc-100">{e.fa}</div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ${e.liq === "high" ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20" : "bg-amber-500/10 text-amber-300 ring-amber-500/20"}`}>{e.liq === "high" ? "نقدشونده" : "متوسط"}</span>
              </div>
              <div className="text-[11px] text-zinc-500 font-mono">{e.sym} • {e.isin}</div>
              <div className="text-xs text-zinc-400 mt-2">کارمزد: {e.fee}% • physical_backed</div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <button onClick={() => { setSigEtf(e.fa); setNavMarket(navMarket); }} className={`rounded-lg py-1.5 ring-1 ${sigEtf === e.fa ? "bg-amber-500/20 text-amber-300 ring-amber-500/30" : "bg-zinc-800/40 text-zinc-400 ring-zinc-700/40"}`}>انتخاب</button>
                <span className="bg-zinc-800/30 rounded-lg py-1.5 text-center text-zinc-500">TSE: {e.fa}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Physical */}
      <section>
        <h2 className="text-sm font-bold text-zinc-200 mb-3">🏅 بازار فیزیکی</h2>
        <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-zinc-900/60 text-[10px] text-zinc-500 border-b border-zinc-800/60"><tr><th className="text-right p-2.5">دارایی</th><th className="text-right p-2.5">وزن</th><th className="text-right p-2.5">عیار</th><th className="text-right p-2.5">منبع</th></tr></thead>
            <tbody>{PHYS.map(r => <tr key={r.fa} className="border-b border-zinc-800/30"><td className="p-2.5 text-zinc-200">{r.fa}</td><td className="p-2.5 text-zinc-400">{r.w}</td><td className="p-2.5 text-zinc-400">{r.p}</td><td className="p-2.5 text-zinc-500">BrsApi.ir</td></tr>)}</tbody>
          </table>
        </div>
        <div className="mt-2 text-[11px] text-zinc-500">اونس جهانی: XAU/USD • 31.1035g • COMEX/LBMA • 23/5</div>
      </section>

      {/* Calculations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* NAV Premium */}
        <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
          <h3 className="text-sm font-bold text-zinc-100 mb-3">🧮 NAV Premium/Discount</h3>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <label className="text-xs text-zinc-400">قیمت بازار<input type="number" value={navMarket} onChange={e => setNavMarket(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
            <label className="text-xs text-zinc-400">NAV<input type="number" value={navNav} onChange={e => setNavNav(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
          </div>
          <div className={`rounded-lg p-3 ring-1 ${navRes.signal === "BUY" ? "bg-emerald-500/10 ring-emerald-500/30 text-emerald-300" : navRes.signal === "SELL" ? "bg-rose-500/10 ring-rose-500/30 text-rose-300" : "bg-zinc-800/40 ring-zinc-700/40 text-zinc-300"}`}>
            <div className="flex justify-between"><span className="text-xs">پرمیوم</span><b className="tabular-nums">{fmtPct(navRes.premium_pct)}</b></div>
            <div className="text-xs mt-1">{navRes.reason}</div>
            <div className="text-[11px] mt-1 opacity-70">آستانه: &gt;2% SELL • &lt;-1% BUY • else NEUTRAL</div>
          </div>
        </div>

        {/* Coin Bubble */}
        <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
          <h3 className="text-sm font-bold text-zinc-100 mb-3">🪙 حباب سکه</h3>
          <label className="text-xs text-zinc-400">قیمت سکه (تومان)<input type="number" value={coinPrice} onChange={e => setCoinPrice(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
          <div className="grid grid-cols-3 gap-2 mt-2 text-[11px] text-zinc-500"><span>اونس: ${fmt(xau)}</span><span>دلار: {fmt(usd)}</span><span>وزن: 8.133g • 0.915</span></div>
          <div className={`mt-3 rounded-lg p-3 ring-1 ${bubbleRes.signal === "BUY" ? "bg-emerald-500/10 ring-emerald-500/30 text-emerald-300" : bubbleRes.signal === "SELL" ? "bg-rose-500/10 ring-rose-500/30 text-rose-300" : "bg-zinc-800/40 ring-zinc-700/40 text-zinc-300"}`}>
            <div className="flex justify-between"><span className="text-xs">حباب</span><b>{fmtPct(bubbleRes.bubble_pct)}</b></div>
            <div className="text-xs mt-1">ذاتی: {fmt(bubbleRes.coin_intrinsic)} ت • {bubbleRes.reason}</div>
            <div className="text-[11px] mt-1 opacity-70">فرمول: (XAU/31.1035)*8.133*0.915*USD • &gt;5% SELL • &lt;-3% BUY</div>
          </div>
        </div>

        {/* Futures Risk */}
        <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
          <h3 className="text-sm font-bold text-zinc-100 mb-3">⚡ مارجین آتی (IME • 10x)</h3>
          <div className="grid grid-cols-3 gap-2">
            <label className="text-xs text-zinc-400">ورود<input type="number" value={futEntry} onChange={e => setFutEntry(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100" /></label>
            <label className="text-xs text-zinc-400">جهت<select value={futType} onChange={e => setFutType(e.target.value as "LONG" | "SHORT")} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100"><option value="LONG">LONG</option><option value="SHORT">SHORT</option></select></label>
            <label className="text-xs text-zinc-400">موجودی<input type="number" value={futEquity} onChange={e => setFutEquity(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100" /></label>
          </div>
          <div className="mt-3 space-y-2 text-xs">
            <div className="flex justify-between bg-zinc-800/40 rounded-lg p-2"><span className="text-zinc-500">لیکوئید</span><b className="text-zinc-100">{fmt(fut.liq)}</b></div>
            <div className="flex justify-between bg-zinc-800/40 rounded-lg p-2"><span className="text-zinc-500">سلامت</span><b className={fut.level === "SAFE" ? "text-emerald-300" : fut.level === "WARNING" ? "text-amber-300" : "text-rose-300"}>{fut.hl.toFixed(2)} • {fut.level}</b></div>
            <div className={`rounded-lg p-2 ring-1 text-xs ${fut.level === "CRITICAL" ? "bg-rose-500/10 ring-rose-500/30 text-rose-300" : fut.level === "WARNING" ? "bg-amber-500/10 ring-amber-500/30 text-amber-300" : "bg-emerald-500/10 ring-emerald-500/30 text-emerald-300"}`}>{fut.msg}</div>
            <div className="text-[11px] text-zinc-500">اولیه 10% • نگهداری 5% • قرارداد 10 سکه • تحویل فیزیکی</div>
          </div>
        </div>

        {/* Dollar-Adjusted */}
        <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
          <h3 className="text-sm font-bold text-zinc-100 mb-3">💵 بازده دلاری (KPI)</h3>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-zinc-400">ارزش ورود (ریال)<input type="number" value={dEntryIrr} onChange={e => setDEntryIrr(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100" /></label>
            <label className="text-xs text-zinc-400">ارزش فعلی (ریال)<input type="number" value={dCurIrr} onChange={e => setDCurIrr(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100" /></label>
            <label className="text-xs text-zinc-400">دلار ورود<input type="number" value={dEntryUsd} onChange={e => setDEntryUsd(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100" /></label>
            <label className="text-xs text-zinc-400">دلار فعلی<input type="number" value={dCurUsd} onChange={e => setDCurUsd(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded px-2 py-1.5 text-xs text-zinc-100" /></label>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div className="bg-zinc-800/40 rounded-lg p-2 text-center"><div className="text-[10px] text-zinc-500">بازده ریالی</div><b className="text-zinc-100">{fmtPct(dRes.irr_roi_pct)}</b></div>
            <div className={`rounded-lg p-2 text-center ring-1 ${dRes.is_beating ? "bg-emerald-500/10 ring-emerald-500/30" : "bg-rose-500/10 ring-rose-500/30"}`}><div className="text-[10px] text-zinc-500">بازده دلاری</div><b className={dRes.is_beating ? "text-emerald-300" : "text-rose-300"}>{fmtPct(dRes.dollar_roi_pct)}</b></div>
            <div className="bg-zinc-800/40 rounded-lg p-2 text-center"><div className="text-[10px] text-zinc-500">رشد دلار</div><b className="text-zinc-100">{fmtPct(dRes.usd_growth_pct)}</b></div>
          </div>
          <div className={`mt-2 rounded-lg p-2 text-xs ring-1 ${dRes.is_beating ? "bg-emerald-500/10 ring-emerald-500/20 text-emerald-300" : "bg-rose-500/10 ring-rose-500/20 text-rose-300"}`}>{dRes.is_beating ? "✅ جلوتر از تورم دلاری" : "❌ عقب از تورم دلاری"} • ${dRes.usdEntry.toFixed(2)} → ${dRes.usdCur.toFixed(2)}</div>
        </div>
      </div>

      {/* Arbitrage */}
      <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
        <h3 className="text-sm font-bold text-zinc-100 mb-3">⚡ موتور آربیتراژ (ETF ↔ فیزیکی)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="text-xs text-zinc-400">قیمت هر گرم ETF<input type="number" value={arbEtf} onChange={e => setArbEtf(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
          <label className="text-xs text-zinc-400">قیمت هر گرم فیزیکی<input type="number" value={arbPhys} onChange={e => setArbPhys(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
          <div className="flex flex-col justify-end"><div className={`rounded-lg p-3 ring-1 text-xs ${arbRes.action === "NO_ARBITRAGE" ? "bg-zinc-800/40 ring-zinc-700/40 text-zinc-400" : "bg-emerald-500/10 ring-emerald-500/30 text-emerald-300"}`}><div>ناخالص: {fmtPct(arbRes.gross_spread_pct)} • خالص: {fmtPct(arbRes.net_spread_pct)}</div><div className="font-bold mt-1">{arbRes.action}</div><div className="text-[11px] opacity-70">{arbRes.strategy}</div></div></div>
        </div>
        <div className="text-[11px] text-zinc-500 mt-2">هزینه 0.3% • آستانه خالص ±1.5%</div>
      </div>

      {/* Kill-Switch controls */}
      <div className="rounded-xl ring-1 p-4" style={{ background: ksStatus === "ACTIVE" ? "rgba(239,68,68,0.1)" : ksStatus === "WARNING" ? "rgba(245,158,11,0.08)" : "rgba(16,185,129,0.06)", borderColor: ksStatus === "ACTIVE" ? "rgba(239,68,68,0.3)" : ksStatus === "WARNING" ? "rgba(245,158,11,0.3)" : "rgba(16,185,129,0.2)" }}>
        <h3 className="text-sm font-bold text-zinc-100 mb-3">🛑 Kill-Switch & Sentiment</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <label className="text-xs text-zinc-400">نوسان اونس 2h%<input type="number" step={0.1} value={ksOunce2h} onChange={e => setKsOunce2h(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
          <label className="text-xs text-zinc-400">نوسان دلار 2h%<input type="number" step={0.1} value={ksUsd2h} onChange={e => setKsUsd2h(+e.target.value)} className="mt-1 w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-2 py-1.5 text-sm text-zinc-100" /></label>
          <label className="flex items-center gap-2 text-xs text-zinc-400 mt-6"><input type="checkbox" checked={ksMargin} onChange={e => setKsMargin(e.target.checked)} /> افزایش وجه تضمین</label>
          <label className="flex items-center gap-2 text-xs text-zinc-400 mt-6"><input type="checkbox" checked={ksFreeze} onChange={e => setKsFreeze(e.target.checked)} /> توقف نمادها</label>
        </div>
        <div className={`mt-3 rounded-lg p-3 text-xs font-bold ring-1 ${ksStatus === "ACTIVE" ? "bg-rose-500/20 text-rose-300 ring-rose-500/30" : ksStatus === "WARNING" ? "bg-amber-500/20 text-amber-300 ring-amber-500/30" : "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20"}`}>
          {ksStatus === "ACTIVE" ? "🔴 KILL_SWITCH_ACTIVE — لغو سفارش‌ها، خروج از آتی، حفظ ETF بدون اهرم" : ksStatus === "WARNING" ? "🟡 WARNING — کاهش اهرم، عدم ورود جدید" : "🟢 NORMAL — شرایط عادی"}
          <div className="font-normal opacity-70 mt-1">منابع: cbi.ir • tsetmc.ir/News • ime.co.ir/News • tasnimnews.com • isna.ir</div>
        </div>
      </div>

      {/* Signal Output — Standard Schema */}
      <section className="rounded-2xl bg-gradient-to-br from-zinc-900 via-zinc-900 to-amber-950/20 ring-1 ring-amber-500/20 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-base font-black text-zinc-100">📋 سیگنال استاندارد (Output Schema)</h2>
          <div className="flex gap-2">
            <select value={sigEtf} onChange={e => setSigEtf(e.target.value)} className="bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-1.5 text-xs text-zinc-100">{ETF.map(e => <option key={e.fa} value={e.fa}>{e.fa} ({e.sym})</option>)}</select>
            <select value={sigLev} onChange={e => setSigLev(+e.target.value)} className="bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-1.5 text-xs text-zinc-100"><option value={1}>1x (ETF)</option><option value={10}>10x (آتی)</option></select>
            <button onClick={() => navigator.clipboard.writeText(JSON.stringify(outputJson, null, 2))} className="text-xs bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 ring-1 ring-amber-500/30 rounded-lg px-3 py-1.5">📋 کپی JSON</button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div className={`rounded-xl p-4 ring-1 text-center ${sigAction === "BUY" ? "bg-emerald-500/10 ring-emerald-500/30" : sigAction === "SELL" ? "bg-rose-500/10 ring-rose-500/30" : sigAction === "CLOSE" ? "bg-rose-600/20 ring-rose-500/40" : "bg-zinc-800/40 ring-zinc-700/40"}`}>
            <div className={`text-2xl font-black ${sigAction === "BUY" ? "text-emerald-300" : sigAction === "SELL" || sigAction === "CLOSE" ? "text-rose-300" : "text-zinc-300"}`}>{sigAction}</div>
            <div className="text-xs text-zinc-400 mt-1">اطمینان: {(sigConf * 100).toFixed(0)}٪ • {outputJson.signal.timeframe}</div>
            <div className="text-[11px] text-zinc-500 mt-1">{chosenEtf.sym} • TSE</div>
          </div>
          <div className="rounded-xl bg-zinc-800/40 ring-1 ring-zinc-700/40 p-3 text-xs space-y-1">
            <div className="flex justify-between"><span className="text-zinc-500">ورود</span><b className="text-zinc-100">{fmt(outputJson.trade_parameters.entry_range[0])} – {fmt(outputJson.trade_parameters.entry_range[1])}</b></div>
            <div className="flex justify-between"><span className="text-zinc-500">حد ضرر</span><b className="text-rose-300">{fmt(outputJson.trade_parameters.stop_loss)}</b></div>
            <div className="flex justify-between"><span className="text-zinc-500">هدف 1</span><b className="text-emerald-300">{fmt(outputJson.trade_parameters.target_1)}</b></div>
            <div className="flex justify-between"><span className="text-zinc-500">هدف 2</span><b className="text-emerald-300">{fmt(outputJson.trade_parameters.target_2)}</b></div>
            <div className="flex justify-between border-t border-zinc-700/40 pt-1"><span className="text-zinc-500">R/R</span><b className="text-amber-300">{outputJson.trade_parameters.risk_reward_ratio.toFixed(2)}</b></div>
          </div>
          <div className="rounded-xl bg-zinc-800/40 ring-1 ring-zinc-700/40 p-3 text-xs space-y-1">
            <div className="flex justify-between"><span className="text-zinc-500">NAV Premium</span><b>{fmtPct(outputJson.metrics.nav_premium_pct)}</b></div>
            <div className="flex justify-between"><span className="text-zinc-500">حباب سکه</span><b>{fmtPct(outputJson.metrics.coin_bubble_pct)}</b></div>
            <div className="flex justify-between"><span className="text-zinc-500">بازده دلاری</span><b className={outputJson.metrics.dollar_adjusted_expected_roi && outputJson.metrics.dollar_adjusted_expected_roi > 0 ? "text-emerald-300" : "text-rose-300"}>{fmtPct(outputJson.metrics.dollar_adjusted_expected_roi)}</b></div>
            <div className="flex justify-between"><span className="text-zinc-500">اهرم</span><b>{outputJson.leverage_and_margin.leverage}x • {outputJson.leverage_and_margin.risk_level}</b></div>
            {outputJson.leverage_and_margin.liquidation_price && <div className="flex justify-between"><span className="text-zinc-500">لیکوئید</span><b className="text-rose-300">{fmt(outputJson.leverage_and_margin.liquidation_price)}</b></div>}
          </div>
        </div>

        <div className="rounded-xl bg-zinc-950/60 ring-1 ring-zinc-800/60 p-3">
          <div className="text-[11px] text-zinc-500 mb-1">rationale</div>
          <div className="text-xs text-zinc-300 leading-relaxed">{outputJson.rationale}</div>
          <div className="text-[11px] text-zinc-500 mt-2">Kill-Switch: {outputJson.kill_switch_status} • بدون اجرای خودکار — Manual Decision Support</div>
        </div>

        <details className="mt-4">
          <summary className="text-xs text-zinc-400 cursor-pointer hover:text-zinc-200">نمایش JSON خام</summary>
          <pre className="mt-2 bg-zinc-950/80 rounded-lg p-3 text-[11px] text-zinc-300 overflow-auto max-h-96 leading-relaxed" dir="ltr">{JSON.stringify(outputJson, null, 2)}</pre>
        </details>
      </section>

      {/* Data Layer */}
      <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4">
        <h3 className="text-sm font-bold text-zinc-100 mb-3">💾 استراتژی ذخیره‌سازی (Data Layer)</h3>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead className="text-[10px] text-zinc-500 border-b border-zinc-800/60"><tr><th className="text-right p-2">نوع داده</th><th className="text-right p-2">دیتابیس</th><th className="text-right p-2">رزولوشن</th><th className="text-right p-2">TTL</th><th className="text-right p-2">منبع</th></tr></thead>
            <tbody className="text-zinc-400">
              <tr className="border-b border-zinc-800/30"><td className="p-2">قیمت Real-time</td><td className="p-2">Redis</td><td className="p-2">1s/5s/1m</td><td className="p-2">5-60s</td><td className="p-2">BrsApi, TSETMC</td></tr>
              <tr className="border-b border-zinc-800/30"><td className="p-2">OHLCV</td><td className="p-2">TimescaleDB</td><td className="p-2">5m/15m/1h/1D</td><td className="p-2">دائمی</td><td className="p-2">BrsApi, TSETMC, IME</td></tr>
              <tr className="border-b border-zinc-800/30"><td className="p-2">سوابق NAV و حباب</td><td className="p-2">TimescaleDB</td><td className="p-2">1m</td><td className="p-2">دائمی</td><td className="p-2">TSETMC / داخلی</td></tr>
              <tr><td className="p-2">پورتفولیو</td><td className="p-2">PostgreSQL</td><td className="p-2">Event-based</td><td className="p-2">دائمی</td><td className="p-2">Manual</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-center text-[11px] text-zinc-500 py-2">⚠️ صرفاً تحلیل شخصی — سیگنال مالی محسوب نمی‌شود • KPI: Dollar-Adjusted Return</div>
    </div>
  );
}
