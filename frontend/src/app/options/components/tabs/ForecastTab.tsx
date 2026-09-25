"use client";

import { useState } from "react";
import { Brain, Loader2, Crosshair, Radar } from "lucide-react";
import { apiGet } from "@/lib/api";
import { fmt } from "../helpers";

interface MoveBand { lower: number; upper: number; median: number }
interface ForecastData {
  symbol: string;
  expected_move?: MoveBand & { analytic_lower?: number; analytic_upper?: number };
  max_pain?: { strike: number; payouts?: { strike: number; payout: number }[] };
  iv_radar?: { strike: number; iv: number }[];
}

function BandChart({ band, spot }: { band: MoveBand; spot: number }) {
  const lo = Math.min(band.lower, spot) * 0.98;
  const hi = Math.max(band.upper, spot) * 1.02;
  const x = (v: number) => 40 + ((v - lo) / (hi - lo || 1)) * 520;
  return (
    <svg viewBox="0 0 600 120" className="w-full bg-slate-950 rounded-xl" style={{ direction: "ltr" }}>
      <rect x={x(band.lower)} y={30} width={Math.max(x(band.upper) - x(band.lower), 2)} height={40} rx={8} fill="rgba(16,185,129,0.15)" stroke="#10b981" strokeWidth={1} strokeDasharray="5" />
      <line x1={x(spot)} y1={15} x2={x(spot)} y2={95} stroke="#fbbf24" strokeWidth={2} />
      <circle cx={x(band.median)} cy={50} r={5} fill="#10b981" />
      <text x={x(spot)} y={110} fill="#94a3b8" fontSize={10} textAnchor="middle" fontFamily="monospace">{fmt(spot)}</text>
      <text x={x(band.lower)} y={20} fill="#10b981" fontSize={10} textAnchor="middle" fontFamily="monospace">{fmt(band.lower)}</text>
      <text x={x(band.upper)} y={20} fill="#10b981" fontSize={10} textAnchor="middle" fontFamily="monospace">{fmt(band.upper)}</text>
    </svg>
  );
}

function IvRadar({ data }: { data: { strike: number; iv: number }[] }) {
  if (data.length < 3) return null;
  const cx = 150, cy = 90, R = 65;
  const maxIv = Math.max(...data.map((d) => d.iv), 0.01);
  const n = data.length;
  const pt = (i: number, v: number) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    const r = (v / maxIv) * R;
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  };
  return (
    <svg viewBox="0 0 300 180" className="w-full bg-slate-950 rounded-xl" style={{ direction: "ltr" }}>
      {[0.33, 0.66, 1].map((f) => (
        <polygon key={f} points={data.map((_, i) => pt(i, maxIv * f)).join(" ")} fill="none" stroke="#334155" strokeWidth={1} />
      ))}
      <polygon points={data.map((d, i) => pt(i, d.iv)).join(" ")} fill="rgba(251,191,36,0.15)" stroke="#fbbf24" strokeWidth={2} />
      {data.map((d, i) => (
        <text key={i} x={+pt(i, maxIv * 1.18).split(",")[0]} y={+pt(i, maxIv * 1.18).split(",")[1]} fill="#94a3b8" fontSize={9} textAnchor="middle" fontFamily="monospace">
          {fmt(d.strike)}
        </text>
      ))}
    </svg>
  );
}

export default function ForecastTab() {
  const [symbol, setSymbol] = useState("فولاد");
  const [data, setData] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiGet<{ success: boolean; data: ForecastData }>(
        `/forecast?symbol=${encodeURIComponent(symbol)}&horizon=30`
      );
      setData(r.success ? r.data : null);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const maxPayout = Math.max(...(data?.max_pain?.payouts ?? [{ payout: 1 }]).map((p) => p.payout), 1);

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="نماد…"
          className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 w-40"
        />
        <button
          onClick={load}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Brain size={14} />}
          پیش‌بینی ۳۰روزه
        </button>
      </div>

      {!data && !loading && (
        <div className="text-center text-slate-500 text-sm py-12">نماد را وارد و پیش‌بینی را اجرا کنید.</div>
      )}

      {data?.expected_move && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
          <h3 className="text-xs font-bold text-slate-300">محدوده حرکت موردانتظار (Expected Move)</h3>
          <BandChart band={data.expected_move} spot={data.expected_move.median} />
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {data?.max_pain && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2"><Crosshair size={14} className="text-rose-400" /> مکث پین (Max Pain)</h3>
            <div className="text-center font-mono text-2xl font-bold text-rose-400" dir="ltr">{fmt(data.max_pain.strike)}</div>
            {(data.max_pain.payouts ?? []).length > 0 && (
              <div className="flex items-end gap-1 h-20" dir="ltr">
                {(data.max_pain.payouts ?? []).slice(0, 20).map((p) => (
                  <div
                    key={p.strike}
                    title={`${p.strike}: ${fmt(p.payout)}`}
                    className={`flex-1 rounded-t ${p.strike === data.max_pain?.strike ? "bg-rose-500" : "bg-slate-700"}`}
                    style={{ height: `${Math.max((p.payout / maxPayout) * 100, 4)}%` }}
                  />
                ))}
              </div>
            )}
          </div>
        )}
        {data?.iv_radar && data.iv_radar.length >= 3 && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2"><Radar size={14} className="text-amber-400" /> رادار نوسان ضمنی (IV)</h3>
            <IvRadar data={data.iv_radar} />
          </div>
        )}
      </div>
    </div>
  );
}
