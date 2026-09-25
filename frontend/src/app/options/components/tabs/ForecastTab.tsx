"use client";

import { useState } from "react";
import { Brain, Loader2 } from "lucide-react";
import { runOptionsPredict, type PredictResponse } from "@/lib/options-api";
import { fmt } from "../helpers";
import { ChartSkeleton } from "./Skeleton";

function BandChart({
  lower68, upper68, lower95, upper95, spot, median,
}: {
  lower68: number; upper68: number; lower95: number; upper95: number; spot: number; median: number;
}) {
  const lo = Math.min(lower95, spot) * 0.97;
  const hi = Math.max(upper95, spot) * 1.03;
  const x = (v: number) => 40 + ((v - lo) / (hi - lo || 1)) * 520;
  return (
    <svg viewBox="0 0 600 140" className="w-full bg-slate-950 rounded-xl" style={{ direction: "ltr" }}>
      <rect x={x(lower95)} y={70} width={Math.max(x(upper95) - x(lower95), 2)} height={40} rx={8} fill="rgba(251,191,36,0.10)" stroke="#fbbf24" strokeWidth={1} strokeDasharray="4" />
      <rect x={x(lower68)} y={80} width={Math.max(x(upper68) - x(lower68), 2)} height={20} rx={6} fill="rgba(16,185,129,0.18)" stroke="#10b981" strokeWidth={1} />
      <line x1={x(spot)} y1={20} x2={x(spot)} y2={125} stroke="#fbbf24" strokeWidth={2} />
      <circle cx={x(median)} cy={90} r={5} fill="#10b981" />
      <text x={x(spot)} y={136} fill="#94a3b8" fontSize={10} textAnchor="middle" fontFamily="monospace">{fmt(spot)}</text>
      <text x={x(lower68)} y={64} fill="#10b981" fontSize={10} textAnchor="middle" fontFamily="monospace">68% ↓ {fmt(lower68)}</text>
      <text x={x(upper68)} y={64} fill="#10b981" fontSize={10} textAnchor="middle" fontFamily="monospace">↑ {fmt(upper68)}</text>
      <text x={x(lower95)} y={30} fill="#fbbf24" fontSize={10} textAnchor="middle" fontFamily="monospace">95% ↓ {fmt(lower95)}</text>
      <text x={x(upper95)} y={30} fill="#fbbf24" fontSize={10} textAnchor="middle" fontFamily="monospace">↑ {fmt(upper95)}</text>
    </svg>
  );
}

function ProbBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-slate-500 w-24 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(Math.max(value * 100, 0), 100)}%` }} />
      </div>
      <span className="font-mono text-xs text-slate-200 w-12 text-left" dir="ltr">{(value * 100).toFixed(1)}%</span>
    </div>
  );
}

export default function ForecastTab() {
  const [symbol, setSymbol] = useState("فولاد");
  const [spot, setSpot] = useState("10000");
  const [sigma, setSigma] = useState("0.35");
  const [dte, setDte] = useState("30");
  const [data, setData] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await runOptionsPredict({
        spot: Number(spot) || 10000,
        sigma: Number(sigma) || 0.35,
        days_to_expiry: Math.max(1, Math.min(365, Number(dte) || 30)),
      });
      if (r.success && r.data) setData(r.data);
      else {
        setData(null);
        setError(r.error?.message ?? "پیش‌بینی ناموفق بود");
      }
    } catch {
      setData(null);
      setError("اتصال به سرور برقرار نشد");
    } finally {
      setLoading(false);
    }
  };

  const mv = data?.expected_move;
  const probs = data?.probabilities;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="نماد"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-32"
        />
        <input value={spot} onChange={(e) => setSpot(e.target.value)} placeholder="قیمت مبنا" inputMode="decimal"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-28 font-mono" dir="ltr" />
        <input value={sigma} onChange={(e) => setSigma(e.target.value)} placeholder="IV" inputMode="decimal"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-20 font-mono" dir="ltr" />
        <input value={dte} onChange={(e) => setDte(e.target.value)} placeholder="DTE" inputMode="numeric"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 w-20 font-mono" dir="ltr" />
        <button
          onClick={load}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Brain size={14} />}
          پیش‌بینی حرکت
        </button>
      </div>

      {error && (
        <div className="text-center text-rose-400 text-xs bg-rose-500/10 border border-rose-500/30 rounded-2xl py-3">{error}</div>
      )}

      {loading && <ChartSkeleton />}

      {!data && !loading && !error && (
        <div className="text-center text-slate-500 text-sm py-12">
          قیمت مبنا و نوسان ضمنی را وارد کنید — باند حرکت مورد انتظار ۶۸٪/۹۵٪ با شبیه‌سازی مانت‌کارلو محاسبه می‌شود.
        </div>
      )}

      {mv && (
        <div className="space-y-3">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
            <div className="text-xs font-bold text-slate-300 mb-2">
              حرکت مورد انتظار {symbol} تا سررسید ({mv.days_to_expiry} روز — {mv.n_paths.toLocaleString("en-US")} مسیر MC)
            </div>
            <BandChart
              lower68={mv.lower_68} upper68={mv.upper_68}
              lower95={mv.lower_95} upper95={mv.upper_95}
              spot={mv.spot} median={mv.median_terminal}
            />
          </div>

          {probs && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
              <div className="text-xs font-bold text-slate-300 mb-1">احتمال‌ها (تنها در تاریخ سررسید قابل اعمال — استایل اروپایی)</div>
              <ProbBar label="احتمال سودآوری (PoP)" value={probs.probability_of_profit} color="bg-emerald-500" />
              <ProbBar label="لمس سقف" value={probs.probability_of_touch_upper} color="bg-amber-500" />
              <ProbBar label="لمس کف" value={probs.probability_of_touch_lower} color="bg-rose-500" />
            </div>
          )}

          {data?.vol_forecast && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-[10px] text-slate-500">نوسان محقق‌شده پیش‌بینی (GARCH)</div>
                <div className="font-mono font-bold text-amber-400" dir="ltr">{(data.vol_forecast.realized_vol_annual * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">نوسان بلندمدت</div>
                <div className="font-mono font-bold text-slate-200" dir="ltr">{(data.vol_forecast.unconditional_vol_annual * 100).toFixed(1)}%</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">IV ورودی</div>
                <div className="font-mono font-bold text-emerald-400" dir="ltr">{(mv.sigma * 100).toFixed(1)}%</div>
              </div>
              <div className="col-span-3 text-[10px] text-slate-600">
                {mv.sigma * 100 > data.vol_forecast.realized_vol_annual * 100 * 1.15
                  ? "پریمیوم آپشن نسبت به نوسان تاریخی گران است (بیش‌ارزش‌گذاری) — استراتژی‌های فروش پریمیوم."
                  : mv.sigma * 100 < data.vol_forecast.realized_vol_annual * 100 * 0.85
                    ? "پریمیوم ارزان است (کم‌ارزش‌گذاری) — استراتژی‌های خرید پریمیوم."
                    : "پریمیوم در محدودهٔ منصفانه نسبت به نوسان محقق‌شده."}
              </div>
            </div>
          )}

          {data?.put_call_ratio !== undefined && data.put_call_ratio > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 text-center">
              <div className="text-[10px] text-slate-500">نسبت پوت به کال (PCR)</div>
              <div className="font-mono font-bold text-2xl text-rose-400" dir="ltr">{data.put_call_ratio.toFixed(2)}</div>
              <div className="text-[10px] text-slate-600">{data.put_call_ratio > 1 ? "احساسات محتاط (هج به پوت بالا)" : "احساسات صعودی‌تر"}</div>
            </div>
          )}

          <div className="text-[10px] text-slate-600 text-center">{data.legal_disclaimer}</div>
        </div>
      )}
    </div>
  );
}
