"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost, extractArray } from "@/lib/api";
import { fa, faDateTime, faPct, isGoldText, isSilverText } from "./helpers";

interface StrategyItem {
  name: string;
  type: string;
  class_name: string;
  params: Record<string, unknown>;
  description: string;
}

interface FundRow {
  symbol?: string;
  name?: string;
  fund_type?: string;
}

interface BacktestRunResponse {
  id: string;
  name: string;
  status: string;
  progress_pct: number;
  message: string;
}

interface EquityPoint {
  timestamp: string;
  nav: number;
  cash: number;
  positions_value: number;
}

interface TradeRow {
  instrument_id: string;
  side: string;
  quantity: number;
  price: number;
  pnl: number;
}

interface BacktestResult {
  id: string;
  name: string;
  status: string;
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  initial_capital: number;
  final_value: number;
  equity_curve: EquityPoint[];
  trades: TradeRow[];
  metrics: Record<string, number>;
  data_quality?: { quality_score: number; warnings: string[] } | null;
  data_source_warning?: string | null;
}

interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { message?: string } | null;
}

function EquityChart({ points, height = 220 }: { points: EquityPoint[]; height?: number }) {
  if (points.length < 2) {
    return <div className="grid h-36 place-items-center rounded-xl bg-soft text-xs text-ink-3">منحنی سرمایه در دسترس نیست.</div>;
  }
  const w = 800;
  const padX = 64;
  const padY = 18;
  const plotR = w - 20;
  const navs = points.map((p) => p.nav);
  const max = Math.max(...navs);
  const min = Math.min(...navs);
  const range = max - min || 1;
  const x = (i: number) => padX + (i / (points.length - 1)) * (plotR - padX);
  const y = (v: number) => padY + (1 - (v - min) / range) * (height - padY * 2);
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.nav).toFixed(1)}`).join(" ");
  const up = navs[navs.length - 1] >= navs[0];
  const color = up ? "#10b981" : "#f43f5e";
  const step = Math.max(1, Math.floor(points.length / 5));

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet" style={{ direction: "ltr" }}>
      <defs>
        <linearGradient id="equity-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${padX},${height - padY} ${line} ${x(points.length - 1)},${height - padY}`} fill="url(#equity-area)" />
      <polyline points={line} fill="none" stroke={color} strokeWidth={2.2} strokeLinejoin="round" />
      <text x={padX - 6} y={padY + 3} fill="#94a3b8" fontSize={10} fontFamily="monospace" textAnchor="end">
        {Math.round(max).toLocaleString("en-US")}
      </text>
      <text x={padX - 6} y={height - padY + 3} fill="#94a3b8" fontSize={10} fontFamily="monospace" textAnchor="end">
        {Math.round(min).toLocaleString("en-US")}
      </text>
      {points.map((p, i) =>
        i % step === 0 ? (
          <text key={`${p.timestamp}-${i}`} x={x(i)} y={height - 4} fill="#94a3b8" fontSize={9} textAnchor="middle">
            {p.timestamp?.slice(0, 10) ?? ""}
          </text>
        ) : null,
      )}
    </svg>
  );
}

export default function BacktestTab() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const yearAgo = useMemo(() => {
    const d = new Date(today);
    d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().slice(0, 10);
  }, [today]);

  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("moving_average_cross");
  const [start, setStart] = useState(yearAgo);
  const [end, setEnd] = useState(today);
  const [capital, setCapital] = useState(100_000_000);
  const [commission, setCommission] = useState(0.35);
  const [slippage, setSlippage] = useState(10);
  const [paramsText, setParamsText] = useState("{}");
  const [paramsError, setParamsError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const strategiesQ = useQuery({
    queryKey: ["silver-backtest-strategies"],
    queryFn: async () => {
      const r = await apiGet<ApiEnvelope<{ items?: StrategyItem[] }>>("/backtests/strategies");
      return extractArray<StrategyItem>(r?.data ?? r);
    },
    staleTime: 600_000,
  });

  const fundsQ = useQuery({
    queryKey: ["silver-funds-for-backtest"],
    queryFn: async () => {
      const r = await apiGet<{ items?: FundRow[]; data?: FundRow[] }>("/funds?market=ime&limit=200");
      const items = extractArray<FundRow>((r as { items?: FundRow[] })?.items ?? (r as { data?: FundRow[] })?.data ?? r);
      const seen = new Set<string>();
      return items.filter((f) => {
        const text = `${f.name ?? ""} ${f.symbol ?? ""}`;
        if (!f.symbol || seen.has(f.symbol)) return false;
        if (!(isSilverText(text) || f.fund_type === "کالایی" || f.fund_type === "نقره")) return false;
        if (isGoldText(text)) return false;
        seen.add(f.symbol);
        return true;
      });
    },
    staleTime: 600_000,
  });

  const runMutation = useMutation({
    mutationFn: async () => {
      let parsed: Record<string, unknown> = {};
      try {
        parsed = JSON.parse(paramsText || "{}") as Record<string, unknown>;
        setParamsError(null);
      } catch {
        setParamsError("پارامترهای JSON نامعتبر است");
        throw new Error("invalid params json");
      }
      setApiError(null);
      const envelope = await apiPost<ApiEnvelope<BacktestRunResponse>>("/backtests/run", {
        name: `نقره — ${strategy}`,
        symbols: [symbol],
        strategy_type: strategy,
        strategy_params: parsed,
        start_date: start,
        end_date: end,
        initial_capital: capital,
        commission_pct: commission / 100,
        slippage_bps: slippage,
        data_source: "auto",
        sizing_method: "fixed",
        sizing_value: 1000,
      });
      if (!envelope.success || !envelope.data) {
        throw new Error(envelope.error?.message ?? "اجرای بک‌تست ناموفق بود");
      }
      return envelope.data;
    },
    onSuccess: (data) => setRunId(data.id),
    onError: (err: Error) => setApiError(err.message),
  });

  const resultQ = useQuery({
    queryKey: ["silver-backtest-result", runId],
    enabled: Boolean(runId),
    queryFn: async () => {
      const r = await apiGet<ApiEnvelope<BacktestResult | null>>(`/backtests/runs/${runId}/result`);
      return r.data ?? null;
    },
  });

  const result = resultQ.data;

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
        <h3 className="text-sm font-black text-ink">بک‌تست استراتژی روی نماد نقره</h3>
        <p className="mt-1 text-[11px] text-ink-3">
          اجرای واقعی موتور بک‌تست روی داده تاریخی نماد انتخابی (بدون داده ساختگی؛ در صورت نبود تاریخچه، خطا نمایش داده می‌شود).
        </p>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-[11px] text-ink-3">
            نماد پایه
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.trim())}
              placeholder="مثلاً نماد صندوق نقره‌ای یا سهام"
              list="silver-symbol-suggestions"
              className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 font-mono text-sm text-ink"
              dir="ltr"
            />
            <datalist id="silver-symbol-suggestions">
              {(fundsQ.data ?? []).map((f) => (
                <option key={f.symbol} value={f.symbol}>
                  {f.name}
                </option>
              ))}
            </datalist>
          </label>

          <label className="text-[11px] text-ink-3">
            استراتژی
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-sm text-ink">
              {(strategiesQ.data ?? []).map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name} {s.type ? `(${s.type})` : ""}
                </option>
              ))}
              {!strategiesQ.data?.length && <option value="moving_average_cross">moving_average_cross</option>}
            </select>
          </label>

          <label className="text-[11px] text-ink-3">
            از تاریخ
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-sm text-ink" dir="ltr" />
          </label>

          <label className="text-[11px] text-ink-3">
            تا تاریخ
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-sm text-ink" dir="ltr" />
          </label>

          <label className="text-[11px] text-ink-3">
            سرمایه اولیه (ریال)
            <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 font-mono text-sm text-ink" dir="ltr" />
          </label>

          <label className="text-[11px] text-ink-3">
            کارمزد (%)
            <input type="number" step="0.01" value={commission} onChange={(e) => setCommission(Number(e.target.value))} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 font-mono text-sm text-ink" dir="ltr" />
          </label>

          <label className="text-[11px] text-ink-3">
            اسلیپیج (bps)
            <input type="number" value={slippage} onChange={(e) => setSlippage(Number(e.target.value))} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 font-mono text-sm text-ink" dir="ltr" />
          </label>

          <label className="text-[11px] text-ink-3 md:col-span-2 xl:col-span-1">
            پارامترهای استراتژی (JSON)
            <input value={paramsText} onChange={(e) => setParamsText(e.target.value)} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 font-mono text-xs text-ink" dir="ltr" />
          </label>
        </div>

        {strategiesQ.data?.find((s) => s.name === strategy)?.params && (
          <p className="mt-2 text-[10px] text-ink-3">
            پارامترهای پذیرفته‌شده: <span className="font-mono" dir="ltr">{JSON.stringify(strategiesQ.data.find((s) => s.name === strategy)?.params)}</span>
          </p>
        )}

        {(paramsError || apiError) && (
          <p className="mt-3 rounded-xl border border-warn/25 bg-warn/5 px-3 py-2 text-[11px] text-warn">{paramsError ?? apiError}</p>
        )}

        <button
          onClick={() => runMutation.mutate()}
          disabled={!symbol || runMutation.isPending}
          className="mt-4 w-full rounded-xl bg-primary-600 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-primary-500 disabled:opacity-50"
        >
          {runMutation.isPending ? "در حال اجرای بک‌تست… (ممکن است چند دقیقه طول بکشد)" : "اجرای بک‌تست"}
        </button>
      </section>

      {resultQ.isLoading && <div className="h-40 animate-pulse rounded-2xl bg-soft" />}

      {resultQ.isError && (
        <p className="rounded-xl border border-warn/25 bg-warn/5 px-3 py-2 text-[11px] text-warn">
          خطا در دریافت نتیجه بک‌تست: {(resultQ.error as Error).message}
        </p>
      )}

      {result && (
        <>
          {result.data_source_warning && (
            <p className="rounded-xl border border-warn/25 bg-warn/5 px-3 py-2 text-[11px] text-warn">{result.data_source_warning}</p>
          )}

          <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            {[
              { l: "بازده کل", v: faPct(result.total_return_pct), tone: result.total_return_pct >= 0 ? "text-up" : "text-down" },
              { l: "بازده سالانه", v: faPct(result.annualized_return_pct), tone: result.annualized_return_pct >= 0 ? "text-up" : "text-down" },
              { l: "شارپ", v: Number(result.sharpe_ratio).toFixed(2), tone: "text-ink" },
              { l: "حداکثر افت", v: faPct(-Math.abs(result.max_drawdown_pct)), tone: "text-down" },
              { l: "نرخ برد", v: `${fa(result.win_rate)}%`, tone: "text-ink" },
              { l: "تعداد معاملات", v: fa(result.total_trades), tone: "text-ink" },
            ].map((m) => (
              <div key={m.l} className="rounded-2xl border border-line bg-card p-3 text-center">
                <p className="text-[10px] text-ink-3">{m.l}</p>
                <p className={`mt-1 font-mono text-sm font-black ${m.tone}`} dir="ltr">{m.v}</p>
              </div>
            ))}
          </section>

          <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-black text-ink">منحنی سرمایه</h3>
              <span className="text-[10px] text-ink-3">
                سرمایه اولیه {fa(result.initial_capital)} → ارزش نهایی {fa(result.final_value)}
              </span>
            </div>
            <div className="rounded-xl bg-soft/60 p-2">
              <EquityChart points={result.equity_curve ?? []} />
            </div>
            <p className="mt-2 text-[10px] text-ink-3">تاریخ تکمیل: {faDateTime((result as { completed_at?: string }).completed_at)}</p>
            {result.data_quality && (
              <p className="mt-1 text-[10px] text-ink-3">
                کیفیت داده: {result.data_quality.quality_score} {result.data_quality.warnings?.length ? `— ${result.data_quality.warnings.slice(0, 2).join(" | ")}` : ""}
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
            <h3 className="mb-3 text-sm font-black text-ink">آخرین معاملات ({fa(result.total_trades)})</h3>
            {result.trades?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-right text-ink-3">
                      <th className="p-2">نماد</th>
                      <th className="p-2">سمت</th>
                      <th className="p-2">تعداد</th>
                      <th className="p-2">قیمت</th>
                      <th className="p-2">سود/زیان</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.slice(-12).reverse().map((t, i) => (
                      <tr key={`${t.instrument_id}-${i}`} className="border-t border-line">
                        <td className="p-2 font-mono">{t.instrument_id}</td>
                        <td className={`p-2 font-bold ${/buy|خرید/i.test(t.side) ? "text-up" : "text-down"}`}>{/buy/i.test(t.side) ? "خرید" : "فروش"}</td>
                        <td className="p-2 font-mono">{fa(t.quantity)}</td>
                        <td className="p-2 font-mono">{fa(t.price)}</td>
                        <td className={`p-2 font-mono ${t.pnl >= 0 ? "text-up" : "text-down"}`}>{fa(Math.round(t.pnl))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-4 text-center text-xs text-ink-3">معامله‌ای در این بازه ثبت نشد.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
