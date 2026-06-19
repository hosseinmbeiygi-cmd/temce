"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import { apiGet } from "@/lib/api";

const SYMBOLS = ["فولاد", "فملی", "شپنا", "وبانک", "خودرو", "ذوب", "رمپنا", "اخابر", "کگل", "چادر"];

export default function FundamentalPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [ratios, setRatios] = useState<any>(null);
  const [score, setScore] = useState<any>(null);
  const [dcf, setDcf] = useState<any>(null);
  const [industry, setIndustry] = useState("فلزات اساسی");
  const [industryData, setIndustryData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"ratios" | "dcf" | "score" | "industry">("ratios");

  async function fetchRatios() {
    setLoading(true);
    try {
      const [r, s, d] = await Promise.all([
        apiGet(`/fundamental/ratios/${symbol}`),
        apiGet(`/fundamental/score/${symbol}`),
        apiGet(`/fundamental/dcf/${symbol}`),
      ]);
      setRatios(r);
      setScore(s);
      setDcf(d);
    } catch {}
    setLoading(false);
  }

  async function fetchIndustry() {
    setLoading(true);
    try {
      const d = await apiGet(`/fundamental/industry/${industry}`);
      setIndustryData(d);
    } catch {}
    setLoading(false);
  }

  const infoRows = (data: any) => [
    { label: "نماد", value: data?.symbol },
    { label: "نام شرکت", value: data?.company_name },
    { label: "صنعت", value: data?.industry },
    { label: "قیمت", value: data?.last_price?.toLocaleString("fa") },
    { label: "ارزش بازار", value: data?.market_cap ? `${(data.market_cap / 1e12).toFixed(2)} تریلیون` : "" },
    { label: "P/E", value: data?.pe, color: data?.pe < 8 ? "text-emerald-400" : data?.pe < 15 ? "text-amber-400" : "text-rose-400" },
    { label: "P/B", value: data?.pb, color: data?.pb < 1 ? "text-emerald-400" : data?.pb < 3 ? "text-amber-400" : "text-rose-400" },
    { label: "ROE", value: data?.roe_pct ? `${data.roe_pct}%` : "", color: data?.roe_pct > 20 ? "text-emerald-400" : data?.roe_pct > 10 ? "text-amber-400" : "text-rose-400" },
    { label: "ROA", value: data?.roa_pct ? `${data.roa_pct}%` : "" },
    { label: "D/E", value: data?.debt_to_equity, color: data?.debt_to_equity < 0.5 ? "text-emerald-400" : data?.debt_to_equity < 1.5 ? "text-amber-400" : "text-rose-400" },
    { label: "EPS", value: data?.eps?.toLocaleString("fa") },
    { label: "BVPS", value: data?.bvps?.toLocaleString("fa") },
    { label: "حاشیه سود", value: data?.net_margin_pct ? `${data.net_margin_pct}%` : "" },
    { label: "سود نقدی", value: data?.dividend_yield_pct ? `${data.dividend_yield_pct}%` : "" },
    { label: "درآمد", value: data?.revenue ? `${(data.revenue / 1e12).toFixed(1)} تریلیون` : "" },
    { label: "سود خالص", value: data?.net_profit ? `${(data.net_profit / 1e12).toFixed(1)} تریلیون` : "" },
  ];

  return (
    <div className="flex min-h-screen bg-surface-950 text-white font-sans" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <h1 className="text-2xl font-bold gradient-text mb-6">تحلیل فاندامنتال</h1>

        <div className="flex gap-2 mb-6">
          {(["ratios", "dcf", "score", "industry"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${tab === t ? "bg-primary-600 text-white" : "bg-surface-800 text-gray-400 hover:text-white"}`}>
              {{ ratios: "نسبت‌های مالی", dcf: "ارزش‌گذاری DCF", score: "امتیازدهی", industry: "تحلیل صنعت" }[t]}
            </button>
          ))}
        </div>

        {(tab === "ratios" || tab === "dcf" || tab === "score") && (
          <div className="flex gap-4 items-end mb-6">
            <div>
              <label className="block text-sm text-gray-400 mb-1">نماد</label>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white">
                {SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <button onClick={fetchRatios} disabled={loading} className="bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg px-6 py-2 text-sm font-medium transition">
              {loading ? "در حال بارگذاری..." : "تحلیل"}
            </button>
          </div>
        )}

        {tab === "ratios" && ratios && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {infoRows(ratios).map((r) => (
              <div key={r.label} className="glass-card p-3">
                <p className="text-xs text-gray-500">{r.label}</p>
                <p className={`text-lg font-semibold ${r.color || ""}`}>{r.value || "-"}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "dcf" && dcf && (
          <div className="space-y-4">
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold mb-4">ارزش‌گذاری DCF - {dcf.symbol}</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 bg-surface-800 rounded-lg">
                  <p className="text-xs text-gray-500">قیمت فعلی</p>
                  <p className="text-lg font-semibold text-rose-400">{dcf.current_price?.toLocaleString("fa")}</p>
                </div>
                <div className="p-3 bg-surface-800 rounded-lg">
                  <p className="text-xs text-gray-500">قیمت منصفانه</p>
                  <p className="text-lg font-semibold text-emerald-400">{dcf.fair_price?.toLocaleString("fa")}</p>
                </div>
                <div className="p-3 bg-surface-800 rounded-lg">
                  <p className="text-xs text-gray-500">پتانسیل رشد</p>
                  <p className={`text-lg font-semibold ${dcf.upside_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {dcf.upside_pct > 0 ? "+" : ""}{dcf.upside_pct}%
                  </p>
                </div>
                <div className="p-3 bg-surface-800 rounded-lg">
                  <p className="text-xs text-gray-500">ارزش بنگاه</p>
                  <p className="text-lg font-semibold">{(dcf.enterprise_value / 1e12).toFixed(1)}T</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4 mt-4">
                <div><p className="text-xs text-gray-500">نرخ رشد</p><p className="font-semibold">{dcf.growth_rate}%</p></div>
                <div><p className="text-xs text-gray-500">WACC</p><p className="font-semibold">{dcf.wacc}%</p></div>
                <div><p className="text-xs text-gray-500">FCF</p><p className="font-semibold">{(dcf.fcf / 1e9).toFixed(0)}M</p></div>
              </div>
            </div>
          </div>
        )}

        {tab === "score" && score && (
          <div className="space-y-4">
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">امتیاز {score.symbol}</h2>
                <div className="text-center">
                  <p className="text-3xl font-bold gradient-text">{score.total_score}</p>
                  <p className="text-xs text-gray-500">از {score.max_score}</p>
                </div>
              </div>
              <div className="w-full bg-surface-800 rounded-full h-3 mb-4">
                <div className="bg-primary-600 h-3 rounded-full transition-all" style={{ width: `${(score.total_score / score.max_score) * 100}%` }} />
              </div>
              <p className="text-center text-lg font-semibold mb-4">تحلیل: {score.rating_fa}</p>
              <div className="space-y-2">
                {score.details?.map((d: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-surface-800 rounded-lg">
                    <div>
                      <p className="text-sm font-medium">{d.factor}</p>
                      <p className="text-xs text-gray-500">{d.desc}</p>
                    </div>
                    <span className={`text-sm font-bold ${d.score > 10 ? "text-emerald-400" : d.score > 5 ? "text-amber-400" : "text-rose-400"}`}>
                      {d.score}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "industry" && (
          <div className="space-y-4">
            <div className="flex gap-4 items-end mb-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">صنعت</label>
                <select value={industry} onChange={(e) => setIndustry(e.target.value)} className="bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white">
                  {["فلزات اساسی", "فرآورده‌های نفتی", "بانک", "خودرو", "پتروشیمی", "سیمان", "دارویی"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <button onClick={fetchIndustry} disabled={loading} className="bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg px-6 py-2 text-sm font-medium transition">
                {loading ? "..." : "تحلیل صنعت"}
              </button>
            </div>

            {industryData && (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <div className="glass-card p-4 text-center">
                    <p className="text-xs text-gray-500">P/E میانگین</p>
                    <p className="text-xl font-bold">{industryData.avg_pe}</p>
                  </div>
                  <div className="glass-card p-4 text-center">
                    <p className="text-xs text-gray-500">P/B میانگین</p>
                    <p className="text-xl font-bold">{industryData.avg_pb}</p>
                  </div>
                  <div className="glass-card p-4 text-center">
                    <p className="text-xs text-gray-500">ROE میانگین</p>
                    <p className="text-xl font-bold">{industryData.avg_roe}%</p>
                  </div>
                </div>
                <div className="glass-card p-4">
                  <h3 className="font-semibold mb-3">شرکت‌های هم‌صنعت ({industryData.peers_count})</h3>
                  <div className="overflow-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-gray-500 border-b border-surface-700">
                          <th className="text-right py-2 px-2">نماد</th>
                          <th className="text-right py-2 px-2">P/E</th>
                          <th className="text-right py-2 px-2">P/B</th>
                          <th className="text-right py-2 px-2">ROE</th>
                          <th className="text-right py-2 px-2">ارزش بازار</th>
                        </tr>
                      </thead>
                      <tbody>
                        {industryData.peers?.map((p: any) => (
                          <tr key={p.symbol} className="border-b border-surface-800 hover:bg-surface-800/50">
                            <td className="py-2 px-2 font-medium">{p.symbol}</td>
                            <td className="py-2 px-2">{p.pe}</td>
                            <td className="py-2 px-2">{p.pb}</td>
                            <td className="py-2 px-2">{p.roe}%</td>
                            <td className="py-2 px-2">{(p.market_cap / 1e12).toFixed(1)}T</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
