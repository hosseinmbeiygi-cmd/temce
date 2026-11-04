"use client";

import { useEffect, useRef, useState } from "react";

import type { GoldWhatIf, TerminalReferences } from "@/types/phase1";

import {
  bubbleTone,
  faNumber,
  faPercent,
  gapTitle,
} from "./format";
import { MissingValue } from "./TerminalBits";

interface WhatIfCalculatorProps {
  references: TerminalReferences | null;
  result: GoldWhatIf | null;
  pending: boolean;
  error: string | null;
  onSubmit: (input: { xau_usd: number; usd_irt_rial: number }) => void;
}

/**
 * ماشین‌حساب «چه می‌شود اگر» — فقط پیش‌نمایش.
 *
 * دو ورودی دستی (XAU/USD و دلار آزاد به ریال) ارزش ذاتی، حباب و USD ضمنی را
 * با موتور فاز ۰ بازمحاسبه می‌کنند. هیچ چیزی ذخیره یا بازنویسی نمی‌شود و
 * خروجی با برچسب SAMPLE می‌آید.
 */
export function WhatIfCalculator({
  references,
  result,
  pending,
  error,
  onSubmit,
}: WhatIfCalculatorProps) {
  const [xauInput, setXauInput] = useState("");
  const [usdInput, setUsdInput] = useState("");
  const touched = useRef(false);

  useEffect(() => {
    if (touched.current) return;
    if (references?.xau_usd != null) setXauInput(String(references.xau_usd));
    if (references?.usd_irt_rial != null) setUsdInput(String(references.usd_irt_rial));
  }, [references]);

  const xau = Number(xauInput);
  const usdRial = Number(usdInput);
  const valid = Number.isFinite(xau) && xau > 0 && Number.isFinite(usdRial) && usdRial > 0;

  return (
    <section aria-labelledby="whatif-heading" className="space-y-3">
      <div>
        <h2 id="whatif-heading" className="text-base font-semibold text-zinc-100">
          ماشین‌حساب سناریو
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          XAU/USD و دلار آزاد را دستی عوض کنید تا ارزش ذاتی، حباب و USD ضمنی
          بازمحاسبه شود. این خروجی پیش‌نمایش است، نه قیمت زنده.
        </p>
      </div>

      <form
        data-testid="what-if-form"
        className="rounded-xl border border-zinc-800/70 bg-zinc-900/40 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) return;
          onSubmit({ xau_usd: xau, usd_irt_rial: usdRial });
        }}
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-400">XAU/USD (دلار بر اونس)</span>
            <input
              type="number"
              inputMode="decimal"
              step="any"
              min="0"
              value={xauInput}
              onChange={(event) => {
                touched.current = true;
                setXauInput(event.target.value);
              }}
              className="w-full rounded-lg border border-zinc-700/60 bg-zinc-800/60 px-3 py-2 text-sm tabular-nums text-zinc-100"
              data-testid="what-if-xau"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-400">دلار آزاد (ریال)</span>
            <input
              type="number"
              inputMode="decimal"
              step="any"
              min="0"
              value={usdInput}
              onChange={(event) => {
                touched.current = true;
                setUsdInput(event.target.value);
              }}
              className="w-full rounded-lg border border-zinc-700/60 bg-zinc-800/60 px-3 py-2 text-sm tabular-nums text-zinc-100"
              data-testid="what-if-usd"
            />
            {valid && (
              <span className="mt-1 block text-[10px] text-zinc-500">
                معادل {faNumber(usdRial / 10)} تومان
              </span>
            )}
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={!valid || pending}
            className="rounded-lg bg-amber-500/20 px-4 py-2 text-sm font-semibold text-amber-300 ring-1 ring-amber-500/40 transition hover:bg-amber-500/30 disabled:opacity-50"
          >
            {pending ? "در حال محاسبه..." : "محاسبه پیش‌نمایش"}
          </button>
          <span className="text-[10px] text-zinc-500">
            فقط خواندن و محاسبه — هیچ سفارشی ثبت نمی‌شود.
          </span>
        </div>

        {error && (
          <p role="alert" className="mt-3 text-xs text-rose-300">
            {error}
          </p>
        )}
      </form>

      {result && (
        <div className="space-y-3" data-testid="what-if-preview">
          <p
            role="status"
            className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-4 py-2 text-xs text-rose-200"
          >
            <span className="ml-1 rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              SAMPLE
            </span>
            پیش‌نمایش سناریو با XAU/USD {faNumber(result.inputs.xau_usd, 2)} و دلار آزاد{" "}
            {faNumber(result.inputs.usd_irt_rial)} ریال. این اعداد قیمت زنده نیستند و ذخیره
            نمی‌شوند.
          </p>

          <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
            <table className="min-w-[980px] w-full text-xs" data-testid="what-if-physical-table">
              <thead className="bg-zinc-900/80 text-zinc-400">
                <tr>
                  <th scope="col" className="px-3 py-2 text-right font-medium">دارایی</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">قیمت بازار</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">ذاتی پایه</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">ذاتی پیش‌نمایش</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">حباب پایه</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">حباب پیش‌نمایش</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی پیش‌نمایش</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {result.physical.map((row) => (
                  <tr key={row.symbol} className="bg-zinc-950/40 align-top">
                    <td className="px-3 py-2 font-semibold text-zinc-200">{row.label}</td>
                    <td className="px-3 py-2 tabular-nums text-zinc-100">
                      {row.market_price === null ? <MissingValue /> : faNumber(row.market_price)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-300">
                      {row.base_intrinsic === null ? <MissingValue /> : faNumber(row.base_intrinsic)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-amber-200">
                      {row.preview_intrinsic === null ? (
                        <MissingValue reason={gapTitle(row.data_gaps)} />
                      ) : (
                        faNumber(row.preview_intrinsic)
                      )}
                    </td>
                    <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.base_bubble_pct)}`}>
                      {row.base_bubble_pct === null ? <MissingValue /> : faPercent(row.base_bubble_pct)}
                    </td>
                    <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.preview_bubble_pct)}`}>
                      {row.preview_bubble_pct === null ? (
                        <MissingValue reason={gapTitle(row.data_gaps)} />
                      ) : (
                        <span className="font-semibold">{faPercent(row.preview_bubble_pct)}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-200">
                      {row.preview_implied_usd === null ? (
                        <MissingValue reason={gapTitle(row.data_gaps)} />
                      ) : (
                        faNumber(row.preview_implied_usd, 2)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
            <table className="min-w-[900px] w-full text-xs" data-testid="what-if-funds-table">
              <thead className="bg-zinc-900/80 text-zinc-400">
                <tr>
                  <th scope="col" className="px-3 py-2 text-right font-medium">صندوق</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">NAV</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">قیمت بازار</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">حباب اسمی (قبل/بعد)</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">حباب واقعی (بعد)</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی (بعد)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {result.funds.map((row) => (
                  <tr key={row.symbol} className="bg-zinc-950/40 align-top">
                    <td className="px-3 py-2">
                      <div className="font-semibold text-zinc-200">{row.name}</div>
                      <div className="text-[10px] text-zinc-500">{row.symbol}</div>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-200">
                      {row.nav === null ? <MissingValue /> : faNumber(row.nav)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-200">
                      {row.market_price === null ? <MissingValue /> : faNumber(row.market_price)}
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      <span className="text-zinc-400">
                        {row.nominal_bubble_pct_before === null
                          ? "—"
                          : faPercent(row.nominal_bubble_pct_before)}
                      </span>
                      <span className="mx-1 text-zinc-600">/</span>
                      <span className="text-zinc-200">
                        {row.nominal_bubble_pct_after === null
                          ? "—"
                          : faPercent(row.nominal_bubble_pct_after)}
                      </span>
                      <div className="mt-0.5 text-[9px] text-zinc-500">NAV-محور؛ بدون تغییر</div>
                    </td>
                    <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.real_bubble_pct_after)}`}>
                      {row.real_bubble_pct_after === null ? (
                        <MissingValue reason="نیاز به ترکیب دارایی صندوق" />
                      ) : (
                        <span className="font-semibold">
                          {faPercent(row.real_bubble_pct_after)}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-200">
                      {row.implied_usd_after === null ? (
                        <MissingValue reason="نیاز به ترکیب دارایی صندوق" />
                      ) : (
                        faNumber(row.implied_usd_after, 2)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
