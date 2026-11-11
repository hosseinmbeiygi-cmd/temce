"use client";

import { useMemo } from "react";
import { Activity, TrendingUp, TrendingDown, Zap, Shield } from "lucide-react";
import { fa } from "./helpers";
import type { Candle } from "./PriceChart";

interface Props {
  candles: Candle[];
}

export default function TechnicalPanel({ candles }: Props) {
  const pivots = useMemo(() => {
    if (candles.length < 2) return null;
    const last = candles[candles.length - 1];
    const prev = candles[candles.length - 2];
    const h = last.high || 0;
    const l = last.low || 0;
    const c = last.close || 0;
    const pp = (h + l + c * 2) / 4; // pivot with close emphasis
    const r1 = 2 * pp - l;
    const s1 = 2 * pp - h;
    const r2 = pp + (h - l);
    const s2 = pp - (h - l);
    const r3 = h + 2 * (pp - l);
    const s3 = l - 2 * (h - pp);
    return { pp, r1, s1, r2, s2, r3, s3 };
  }, [candles]);

  const rsi = useMemo(() => {
    if (candles.length < 2) return null;
    const close = candles.map((c) => c.close);
    const gains: number[] = [];
    const losses: number[] = [];
    for (let i = 1; i < close.length; i++) {
      const diff = close[i] - close[i - 1];
      gains.push(Math.max(diff, 0));
      losses.push(Math.max(-diff, 0));
    }
    if (gains.length === 0) return null;
    const avgGain = gains.reduce((a, b) => a + b, 0) / gains.length;
    const avgLoss = losses.reduce((a, b) => a + b, 0) / losses.length;
    if (avgLoss === 0) return 70;
    const rs = avgGain / avgLoss;
    return 100 - 100 / (1 + rs);
  }, [candles]);

  const macdInterpretation = useMemo(() => {
    if (candles.length < 4) return null;
    const close = candles.map((c) => c.close);
    const ema = (series: number[], span: number) => {
      const k = 2 / (span + 1);
      const out = series.slice(0, span - 1).map(() => 0);
      let prev = series.slice(0, span).reduce((a, b) => a + b, 0) / span;
      out.push(prev);
      for (let i = span; i < series.length; i++) {
        const cur = series[i] * k + prev * (1 - k);
        out.push(cur);
        prev = cur;
      }
      return out;
    };
    const ema12 = ema(close, 12);
    const ema26 = ema(close, 26);
    const macd = ema12.map((v, i) => v - ema26[i]);
    const signal = ema(macd, 9);
    const hist = macd.map((v, i) => v - signal[i]);
    const lastHist = hist[hist.length - 1] || 0;
    const prevHist = hist[hist.length - 2] || 0;
    let tone = "text-ink-3";
    let note = "ندارد";
    if (lastHist > 0 && prevHist <= 0) {
      tone = "text-up";
      note = " MACD صعودی; سیگنال ضعیف صعودی";
    } else if (lastHist < 0 && prevHist >= 0) {
      tone = "text-down";
      note = " MACD نزولی; سیگنال ضعیف نزولی";
    } else if (lastHist > 0) {
      tone = "text-up";
      note = " MACD صعودی";
    } else {
      tone = "text-down";
      note = " MACD نزولی";
    }
    return { tone, note, lastHist };
  }, [candles]);

  const rsiStatus = rsi == null ? null : rsi >= 70 ? "اشباع فروش" : rsi <= 30 ? "اشباع خرید" : "طبیعی";
  const rsiTone = rsi == null ? "text-ink-3" : rsi >= 70 ? "text-down" : rsi <= 30 ? "text-up" : "text-ink";

  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="mb-4 flex items-center gap-2">
        <Activity className="size-4 text-primary-500" />
        <h3 className="text-sm font-black text-ink">سطوح حمایت / مقاومت + اندیکاتورهای قدرت</h3>
      </div>

      {pivots ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><TrendingUp className="size-4" /> مقاومت R3</span>
              <b className="font-mono text-down" dir="ltr">{fa(pivots.r3)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><TrendingUp className="size-4" /> مقاومت R2</span>
              <b className="font-mono text-down" dir="ltr">{fa(pivots.r2)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><Zap className="size-4" /> مقاومت R1</span>
              <b className="font-mono text-down" dir="ltr">{fa(pivots.r1)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><Activity className="size-4" /> لیدر پایه (Pivot)</span>
              <b className="font-mono text-ink" dir="ltr">{fa(pivots.pp)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><TrendingDown className="size-4" /> حمایت S1</span>
              <b className="font-mono text-up" dir="ltr">{fa(pivots.s1)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><TrendingDown className="size-4" /> حمایت S2</span>
              <b className="font-mono text-up" dir="ltr">{fa(pivots.s2)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><TrendingDown className="size-4" /> حمایت S3</span>
              <b className="font-mono text-up" dir="ltr">{fa(pivots.s3)}</b>
            </div>
            <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink-3"><Shield className="size-4" /> RSI</span>
              <b className={`font-mono ${rsiTone}`} dir="ltr">{rsi == null ? "—" : rsi.toFixed(1) + " — " + rsiStatus}</b>
            </div>
          </div>

          <div className="rounded-xl border border-line bg-soft/30 px-3 py-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-ink-3">تفسیر MACD:</span>
              <span className={macdInterpretation?.tone ?? "text-ink-3"}>{macdInterpretation?.note ?? "—"}</span>
            </div>
            {macdInterpretation?.lastHist != null && (
              <div className="mt-1 font-mono text-[10px]" dir="ltr">
                هیستوگرام MACD: {macdInterpretation.lastHist >= 0 ? "+" : ""}{macdInterpretation.lastHist.toFixed(2)}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="py-6 text-center text-xs text-ink-3">داده تاریخی کافی برای محاسبه پيوت وجود ندارد.</div>
      )}
    </div>
  );
}
