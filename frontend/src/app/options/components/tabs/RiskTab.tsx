"use client";

import { useState } from "react";
import { ShieldCheck, Loader2, Wallet } from "lucide-react";
import { apiGet } from "@/lib/api";
import { fmt } from "../helpers";

interface Greeks {
  delta: number; gamma: number; theta: number; vega: number; rho: number;
  vanna?: number; charm?: number;
  intrinsic_value: number; time_value: number;
}

const GREEK_META = [
  { id: "delta", label: "دلتا", desc: "حساسیت به قیمت مبنا" },
  { id: "gamma", label: "گاما", desc: "تغییر دلتا" },
  { id: "theta", label: "تتا", desc: "فرسایش زمانی روزانه" },
  { id: "vega", label: "وگا", desc: "حساسیت به نوسان" },
  { id: "rho", label: "رو", desc: "حساسیت به نرخ بهره" },
  { id: "vanna", label: "ونا", desc: "حساسیت دلتا به نوسان" },
  { id: "charm", label: "چارم", desc: "فرسایش دلتا در زمان" },
] as const;

export default function RiskTab() {
  const [form, setForm] = useState({ S: "1000", K: "1000", T: "0.25", r: "0.25", sigma: "0.35", qty: "1", size: "1000" });
  const [greeks, setGreeks] = useState<Greeks | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const calc = async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams({
        S: form.S, K: form.K, T: form.T, r: form.r, sigma: form.sigma, option_type: "call",
      });
      const r = await apiGet<{ success: boolean; data: Greeks; error?: { message?: string } }>(
        `/options/greeks?${qs.toString()}`
      );
      if (r.success) setGreeks(r.data);
      else {
        setGreeks(null);
        setError(r.error?.message ?? "خطا در محاسبه");
      }
    } catch {
      setGreeks(null);
      setError("اتصال به سرور برقرار نشد");
    } finally {
      setLoading(false);
    }
  };

  const qty = Number(form.qty) || 0;
  const size = Number(form.size) || 0;
  const margin = greeks ? Math.abs(greeks.delta) * (Number(form.S) || 0) * qty * size * 0.25 : 0;

  const inputs: { id: keyof typeof form; label: string }[] = [
    { id: "S", label: "قیمت مبنا (S)" },
    { id: "K", label: "اعمال (K)" },
    { id: "T", label: "زمان/سال (T)" },
    { id: "r", label: "نرخ (r)" },
    { id: "sigma", label: "نوسان (σ)" },
    { id: "qty", label: "تعداد" },
    { id: "size", label: "اندازه قرارداد" },
  ];

  return (
    <div className="space-y-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {inputs.map((f) => (
            <label key={f.id} className="space-y-1">
              <span className="text-[10px] text-slate-500">{f.label}</span>
              <input
                value={form[f.id]}
                onChange={set(f.id)}
                inputMode="decimal"
                dir="ltr"
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-slate-200"
              />
            </label>
          ))}
          <div className="flex items-end">
            <button
              onClick={calc}
              disabled={loading}
              className="w-full px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              محاسبه
            </button>
          </div>
        </div>
        {error && <div className="mt-2 text-xs text-rose-400">{error}</div>}
      </div>

      {greeks && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
            {GREEK_META.map((g) => (
              <div key={g.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-3 text-center">
                <div className="text-[10px] text-slate-500">{g.label}</div>
                <div className="font-mono font-bold text-slate-100" dir="ltr">
                  {fmt(greeks[g.id as keyof Greeks])}
                </div>
                <div className="text-[9px] text-slate-600">{g.desc}</div>
              </div>
            ))}
          </div>
          <div className="bg-slate-900 border border-amber-500/30 rounded-2xl p-4 flex items-center gap-3">
            <Wallet size={20} className="text-amber-400 shrink-0" />
            <div>
              <div className="text-[10px] text-slate-500">وجه تضمین تقریبی (۲۵٪ ارزش دلتایی موقعیت)</div>
              <div className="font-mono font-bold text-amber-400 text-lg" dir="ltr">{fmt(Math.round(margin))}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
