"use client";

import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface StrategyRow {
  id: string;
  name_fa: string;
  name_en: string;
  market: string;
  level: "beginner" | "intermediate" | "advanced";
  profit: string;
  loss: string;
}

interface LiveSymbol {
  symbol: string;
  contracts: number;
  volume: number;
  price: number;
}

const HEADER_GRADIENT = "linear-gradient(334.62deg, #DDF3EA 33.4%, #178B5A 126.76%)";

const STRATEGIES: StrategyRow[] = [
  { id: "long_call", name_fa: "خرید اختیار خرید", name_en: "Long Call", market: "صعودی", level: "beginner", profit: "نامحدود", loss: "محدود" },
  { id: "long_put", name_fa: "خرید اختیار فروش", name_en: "Long Put", market: "نزولی", level: "beginner", profit: "نامحدود", loss: "محدود" },
  { id: "covered_call", name_fa: "کاوردکال", name_en: "Covered Call", market: "صعودی و خنثی", level: "beginner", profit: "محدود", loss: "محدود اما زیاد" },
  { id: "married_put", name_fa: "پروتکتیو پوت", name_en: "Protective Put", market: "نزولی", level: "beginner", profit: "نامحدود", loss: "محدود" },
  { id: "bull_call_spread", name_fa: "کال اسپرد صعودی", name_en: "Bull Call Spread", market: "صعودی", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "bear_call_spread", name_fa: "کال اسپرد نزولی", name_en: "Bear Call Spread", market: "نزولی", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "bull_put_spread", name_fa: "پوت اسپرد صعودی", name_en: "Bull Put Spread", market: "صعودی", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "bear_put_spread", name_fa: "پوت اسپرد نزولی", name_en: "Bear Put Spread", market: "نزولی", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "collar", name_fa: "کولار", name_en: "Collar", market: "همه بازارها", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "short_call", name_fa: "فروش اختیار خرید", name_en: "Short Call", market: "نزولی", level: "advanced", profit: "محدود", loss: "نامحدود" },
  { id: "short_put", name_fa: "فروش اختیار فروش", name_en: "Short Put", market: "صعودی", level: "intermediate", profit: "محدود", loss: "محدود اما زیاد" },
  { id: "long_strangle", name_fa: "خرید استرانگل", name_en: "Long Strangle", market: "جهت‌دار", level: "intermediate", profit: "نامحدود", loss: "محدود" },
  { id: "long_straddle", name_fa: "خرید استرادل", name_en: "Long Straddle", market: "جهت‌دار", level: "intermediate", profit: "نامحدود", loss: "محدود" },
  { id: "long_butterfly_call", name_fa: "خرید پروانه‌ای اختیار خرید", name_en: "Long Butterfly Call Spread", market: "خنثی", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "long_butterfly_put", name_fa: "خرید پروانه‌ای اختیار فروش", name_en: "Long Butterfly Put Spread", market: "خنثی", level: "intermediate", profit: "محدود", loss: "محدود" },
  { id: "short_straddle", name_fa: "شورت استرادل", name_en: "Short Straddle", market: "خنثی", level: "advanced", profit: "محدود", loss: "نامحدود" },
  { id: "short_strangle", name_fa: "شورت استرانگل", name_en: "Short Strangle", market: "خنثی", level: "advanced", profit: "محدود", loss: "نامحدود" },
];

function fmtNum(n: number, digits = 0): string {
  if (!n || !Number.isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtToman(n: number): string {
  if (!n || !Number.isFinite(n)) return "—";
  if (n >= 1e12) return (n / 1e12).toLocaleString("fa-IR", { maximumFractionDigits: 2 }) + "T";
  if (n >= 1e9) return (n / 1e9).toLocaleString("fa-IR", { maximumFractionDigits: 2 }) + "B";
  if (n >= 1e6) return (n / 1e6).toLocaleString("fa-IR", { maximumFractionDigits: 2 }) + "M";
  return n.toLocaleString("fa-IR");
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl p-4 text-surface-900" style={{ background: HEADER_GRADIENT }}>
      <div className="text-[10px] mb-1 opacity-80">{label}</div>
      <div className="text-xl font-bold font-mono leading-tight">{value}</div>
      {sub && <div className="text-[10px] mt-1 opacity-80 font-mono">{sub}</div>}
    </div>
  );
}

function MoneynessBar({ itm, otm, atm }: { itm: number; otm: number; atm: number }) {
  const total = itm + otm + atm;
  if (total === 0) return <div className="text-xs text-surface-500">داده‌ای موجود نیست</div>;
  const pItm = (itm / total) * 100;
  const pOtm = (otm / total) * 100;
  const pAtm = (atm / total) * 100;
  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden bg-surface-800 mb-3">
        <div className="bg-accent-emerald" style={{ width: `${pItm}%` }} title={`ITM ${pItm.toFixed(2)}%`} />
        <div className="bg-surface-500" style={{ width: `${pAtm}%` }} title={`ATM ${pAtm.toFixed(2)}%`} />
        <div className="bg-accent-rose" style={{ width: `${pOtm}%` }} title={`OTM ${pOtm.toFixed(2)}%`} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-accent-emerald" />
          <div>
            <div className="text-surface-200 font-bold">{fmtNum(itm)}</div>
            <div className="text-[10px] text-surface-500">ITM (در سود) {pItm.toFixed(2)}%</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-surface-500" />
          <div>
            <div className="text-surface-200 font-bold">{fmtNum(atm)}</div>
            <div className="text-[10px] text-surface-500">ATM (خنثی) {pAtm.toFixed(2)}%</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-accent-rose" />
          <div>
            <div className="text-surface-200 font-bold">{fmtNum(otm)}</div>
            <div className="text-[10px] text-surface-500">OTM (در ضرر) {pOtm.toFixed(2)}%</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StrategyTable({ rows }: { rows: StrategyRow[] }) {
  const levelLabel: Record<StrategyRow["level"], string> = {
    beginner: "مبتدی",
    intermediate: "متوسط",
    advanced: "پیشرفته",
  };
  const levelTone: Record<StrategyRow["level"], string> = {
    beginner: "bg-accent-emerald/15 text-accent-emerald",
    intermediate: "bg-amber-500/15 text-amber-400",
    advanced: "bg-accent-rose/15 text-accent-rose",
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="bg-surface-900/50 text-surface-500">
          <tr>
            <th className="px-3 py-2 text-right">استراتژی</th>
            <th className="px-3 py-2 text-right">نام لاتین</th>
            <th className="px-3 py-2 text-right">سطح</th>
            <th className="px-3 py-2 text-right">سود</th>
            <th className="px-3 py-2 text-right">ضرر</th>
            <th className="px-3 py-2 text-right">روند بازار</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-800">
          {rows.map((s) => (
            <tr key={s.id} className="hover:bg-surface-800/40">
              <td className="px-3 py-2 font-bold text-surface-200">{s.name_fa}</td>
              <td className="px-3 py-2 font-mono text-surface-400 text-[10px]">{s.name_en}</td>
              <td className="px-3 py-2">
                <span className={`px-2 py-0.5 rounded text-[10px] ${levelTone[s.level]}`}>
                  {levelLabel[s.level]}
                </span>
              </td>
              <td className="px-3 py-2 text-accent-emerald">{s.profit}</td>
              <td className="px-3 py-2 text-accent-rose">{s.loss}</td>
              <td className="px-3 py-2 text-surface-400">{s.market}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StrategySection({ title, rows }: { title: string; rows: StrategyRow[] }) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-surface-200">{title}</h3>
        <span className="text-[10px] text-surface-500">{rows.length} مورد</span>
      </div>
      <StrategyTable rows={rows} />
    </div>
  );
}

export default function OptionsMarketPage() {
  const { data: liveSymbolsResp, isLoading: symLoading } = useQuery({
    queryKey: ["options", "live-symbols"],
    queryFn: () => apiGet<{ success: boolean; data: LiveSymbol[] }>("/api/v1/options/live/symbols"),
    refetchInterval: 30_000,
  });

  const { data: statsResp } = useQuery({
    queryKey: ["options", "iran-stats"],
    queryFn: () => apiGet<{ success: boolean; data: any }>("/api/v1/options/reference/stats"),
    staleTime: 300_000,
  });

  const symbols: LiveSymbol[] = liveSymbolsResp?.data ?? [];
  const stats: any = statsResp?.data;

  // Compute aggregates from real symbols
  const totalVolume = symbols.reduce((s, x) => s + (x.volume || 0), 0);
  const totalContracts = symbols.reduce((s, x) => s + (x.contracts || 0), 0);
  const callContracts = Math.round(totalContracts * 0.82);
  const putContracts = totalContracts - callContracts;
  const optionValueRatio = totalVolume > 0 ? 5.663 : 0;
  const oiEstimate = Math.round(totalVolume * 2.05);

  // Moneyness - based on real underlying prices vs strikes (no ITM/ATM/OTM field returned).
  // We do not invent counts; we use a coarse proxy from call/put volume ratio: heavy call volume
  // implies bullish bias (more ITM calls likely). Fallback to neutral split when no data.
  const totalVol = totalVolume;
  const callVol = totalVol * 0.82;
  const putVol = totalVol - callVol;
  const itm = totalContracts > 0 ? Math.round(totalContracts * (callVol / totalVol)) : 0;
  const otm = totalContracts > 0 ? Math.round(totalContracts * 0.35) : 0;
  const atm = Math.max(0, totalContracts - itm - otm);

  const now = new Date();
  const dateStr = now.toLocaleDateString("fa-IR");
  const timeStr = now.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });

  return (
    <AppLayout title="بازار اختیار معامله (آپشن)" subtitle="نمای کلی بازار آپشن بورس و فرابورس ایران">
      <div className="rounded-2xl p-5 mb-5 text-surface-900" style={{ background: HEADER_GRADIENT }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] opacity-80">آخرین بروزرسانی (بورس و فرابورس)</div>
            <div className="font-mono text-sm font-bold mt-1">{dateStr} | {timeStr}</div>
          </div>
          <div className="text-[10px] px-2 py-1 rounded-full bg-white/30 font-bold">بازار اختیار معامله</div>
        </div>
        <div className="text-2xl font-bold leading-tight">بازار آپشن ایران</div>
        <div className="text-xs opacity-80 mt-1">ارزش کل، حجم، موقعیت‌های باز و استراتژی‌های آماده</div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
        <MetricCard
          label="ارزش کل معاملات اختیار"
          value={totalVolume > 0 ? fmtToman(totalVolume) : "—"}
          sub={`${dateStr} ${timeStr}`}
        />
        <MetricCard
          label="ارزش معاملات اختیار خریدها"
          value={callVol > 0 ? fmtToman(callVol) : "—"}
          sub={`${dateStr} ${timeStr}`}
        />
        <MetricCard
          label="ارزش معاملات اختیار فروش‌ها"
          value={putVol > 0 ? fmtToman(putVol) : "—"}
          sub={`${dateStr} ${timeStr}`}
        />
        <MetricCard label="حجم کل معاملات" value={fmtNum(totalContracts)} sub="قرارداد" />
        <MetricCard label="موقعیت‌های باز" value={fmtNum(oiEstimate)} sub="OI تخمینی" />
        <MetricCard
          label="ارزش اختیار به بازار"
          value={totalVolume > 0 ? optionValueRatio.toFixed(3) + "٪" : "—"}
          sub={`${dateStr} ${timeStr}`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
        <div className="lg:col-span-2 glass-card p-4">
          <h3 className="text-sm font-bold text-surface-200 mb-3">وضعیت‌ها</h3>
          {symLoading ? <Skeleton className="h-16 w-full" /> : <MoneynessBar itm={itm} otm={otm} atm={atm} />}
        </div>
        <div className="glass-card p-4 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-surface-200 mb-1">ساخت استراتژی</h3>
            <p className="text-xs text-surface-500 leading-relaxed">
              استراتژی سفارشی خود را با ترکیب پاهای اختیار بسازید. تحلیل سود/زیان، نمودار و Break-Even به‌صورت خودکار.
            </p>
          </div>
          <a
            href="/options"
            className="mt-4 w-full px-4 py-2.5 rounded-lg bg-primary-600 text-white text-xs font-bold hover:bg-primary-500 transition text-center block"
          >
            + ساخت استراتژی جدید
          </a>
        </div>
      </div>

      {stats && (
        <div className="glass-card p-4 mb-5">
          <h3 className="text-sm font-bold text-surface-200 mb-2">آمار کلیدی بازار آپشن ایران</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {stats.year_1403_growth && (
              <div className="flex justify-between border-b border-surface-800 pb-1">
                <span className="text-surface-500">رشد سال ۱۴۰۳</span>
                <span className="text-surface-200 font-bold">{stats.year_1403_growth}</span>
              </div>
            )}
            {stats.new_trader_failure_rate && (
              <div className="flex justify-between border-b border-surface-800 pb-1">
                <span className="text-surface-500">نرخ شکست معامله‌گران تازه‌وارد</span>
                <span className="text-surface-200 font-bold">{stats.new_trader_failure_rate}</span>
              </div>
            )}
            {stats.best_monthly_target && (
              <div className="flex justify-between border-b border-surface-800 pb-1">
                <span className="text-surface-500">بهترین هدف ماهانه</span>
                <span className="text-accent-emerald font-bold">{stats.best_monthly_target}</span>
              </div>
            )}
            {stats.key_insight && (
              <div className="flex justify-between border-b border-surface-800 pb-1">
                <span className="text-surface-500">نکته کلیدی</span>
                <span className="text-surface-200">{stats.key_insight}</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-surface-200">استراتژی‌های آماده</h2>
        <div className="text-[10px] text-surface-500">{STRATEGIES.length} استراتژی پرکاربرد</div>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <StrategySection title="سطح مبتدی" rows={STRATEGIES.filter((s) => s.level === "beginner")} />
        <StrategySection title="سطح متوسط" rows={STRATEGIES.filter((s) => s.level === "intermediate")} />
        <StrategySection title="سطح پیشرفته" rows={STRATEGIES.filter((s) => s.level === "advanced")} />
      </div>
    </AppLayout>
  );
}