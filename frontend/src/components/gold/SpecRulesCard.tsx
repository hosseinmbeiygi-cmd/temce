"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Clock3, Loader2, Scale, ShieldCheck } from "lucide-react";
import { useAssistantRules } from "@/hooks/useAssistantRules";
import {
  DISCLAIMER,
  PHYSICAL_DELIVERY_NOTE,
  PROVENANCE_LABEL,
  SESSION_STATE_LABEL,
  SIGNAL_VERDICT_LABEL,
  evaluateTrade,
  feeTerms,
  requiredGrossMovePctFor,
  roundTripFeePct,
  sessionState,
  settlementLabel,
  tehranClock,
  type AssistantRules,
  type InstrumentKind,
  type SignalVerdict,
} from "@/lib/gold-silver-spec";

const fa = (n: number | null | undefined, digits = 2): string =>
  n == null || Number.isNaN(n) ? "—" : n.toLocaleString("fa-IR", { maximumFractionDigits: digits });

// متن احکام یک‌جا در `gold-silver-spec` است تا صفحهٔ طلا، صفحهٔ نقره و این کارت
// یک واژه برای یک معنا به کار ببرند.
const VERDICT_STYLE: Record<SignalVerdict, { label: string; cls: string }> = {
  opportunity: { label: SIGNAL_VERDICT_LABEL.opportunity, cls: "bg-up/15 text-up" },
  watch: { label: SIGNAL_VERDICT_LABEL.watch, cls: "bg-warn/15 text-warn" },
  reject: { label: SIGNAL_VERDICT_LABEL.reject, cls: "bg-down/15 text-down" },
};

/**
 * کارت قواعد طلا و نقره — نمایشی محض.
 *
 * همهٔ اعداد از `rules` می‌آیند که API سرو می‌کند (`acceptance.yaml` تنها منبع)،
 * پس نه تعرفه‌ای در این کامپوننت هاردکد است و نه آستانه‌ای. دو چیز را نشان می‌دهد
 * که سند الزام کرده:
 *  ۱. ساعت، دامنه و تسویهٔ بازار ایران (§۲۷.۳)
 *  ۲. فیلتر ارزش معامله با محاسبهٔ زندهٔ `W`، `L`، `RR` و `EV` (§۲۰ و §۲۶)
 *
 * هر عدد با منشأ خودش برچسب می‌خورد؛ فرض‌ها با پرچم «منتظر تأیید» می‌آیند (§۲۸.۲).
 */
export default function SpecRulesCard({
  rules,
  defaultFeeKind = "commodity_fund",
  className = "",
}: {
  rules: AssistantRules;
  defaultFeeKind?: InstrumentKind;
  className?: string;
}) {
  const [session, setSession] = useState<{ day: 0 | 1 | 2 | 3 | 4 | 5 | 6; hhmm: string } | null>(
    null,
  );

  const hours = rules.market_hours;
  const filter = rules.signal_filter;
  const tripPct = roundTripFeePct(rules, defaultFeeKind);
  const requiredMove = requiredGrossMovePctFor(rules, defaultFeeKind);
  const fee = feeTerms(rules, defaultFeeKind);

  const [entry, setEntry] = useState("100");
  const [target, setTarget] = useState("104");
  const [stop, setStop] = useState("99");
  const [cost, setCost] = useState(tripPct == null ? "" : tripPct.toFixed(2));
  const [probability, setProbability] = useState("");

  // ساعت تهران فقط سمت کلاینت خوانده می‌شود تا هیدریشن ناهمخوان نشود.
  useEffect(() => {
    const tick = () => setSession(tehranClock());
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  const state = session ? sessionState(hours, session.day, session.hhmm) : null;

  const evaluation = useMemo(() => {
    const p = probability.trim() === "" ? null : Number(probability) / 100;
    return evaluateTrade({
      entry: Number(entry),
      target: Number(target),
      stop: Number(stop),
      costPct: cost.trim() === "" ? Number.NaN : Number(cost),
      probability: p,
      filter,
    });
  }, [entry, target, stop, cost, probability, filter]);

  const verdict = VERDICT_STYLE[evaluation.verdict];

  return (
    <div
      className={`rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5 ${className}`}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale className="size-4 text-primary-500" />
          <h3 className="text-sm font-black text-ink">قواعد بازار و فیلتر ارزش معامله</h3>
        </div>
        <span className="rounded-lg bg-soft px-2 py-1 text-[10px] text-ink-3">
          منبع: `acceptance.yaml` نسخهٔ {rules.version} — §۲۰، §۲۶، §۲۷.۱، §۲۷.۳
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ── §۲۷.۳ ساعت، دامنه، تسویه ── */}
        <div className="rounded-xl bg-soft/60 p-3">
          <div className="mb-2 flex items-center gap-2">
            <Clock3 className="size-3.5 text-primary-500" />
            <span className="text-xs font-black text-ink">ساعت و قواعد بازار</span>
            {session && (
              <span
                className="rounded-md bg-card px-1.5 py-0.5 font-mono text-[10px] text-ink-2"
                dir="ltr"
              >
                {session.hhmm}
              </span>
            )}
            {state && (
              <span
                className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                  state === "open"
                    ? "bg-up/15 text-up"
                    : state === "after_close"
                      ? "bg-down/15 text-down"
                      : "bg-warn/15 text-warn"
                }`}
              >
                {SESSION_STATE_LABEL[state]}
              </span>
            )}
            {session && !state && (
              <span className="rounded-md bg-down/15 px-1.5 py-0.5 text-[10px] font-bold text-down">
                {SESSION_STATE_LABEL.holiday}
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center justify-between rounded-lg bg-card px-2 py-1.5">
              <span className="text-ink-3">شنبه تا چهارشنبه</span>
              <b className="font-mono text-ink-2" dir="ltr">
                {hours.sat_to_wed.pre_open} → {hours.sat_to_wed.open} → {hours.sat_to_wed.close}
              </b>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-card px-2 py-1.5">
              <span className="text-ink-3">پنجشنبه (جلسهٔ کوتاه)</span>
              <b className="font-mono text-ink-2" dir="ltr">
                {hours.thursday.pre_open} → {hours.thursday.open} → {hours.thursday.close}
              </b>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-card px-2 py-1.5">
              <span className="text-ink-3">دامنهٔ نوسان روز</span>
              <b className="font-mono text-ink-2" dir="ltr">
                ±{fa(hours.price_band_pct, 0)}٪
              </b>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-card px-2 py-1.5">
              <span className="text-ink-3">تسویه</span>
              <b className="font-mono text-ink-2" dir="ltr">
                {settlementLabel(hours.settlement_days)}
              </b>
            </div>
          </div>

          <p className="mt-2 text-[10px] leading-relaxed text-ink-3">
            دامنه‌های اضطراری{" "}
            {hours.emergency_band_pcts.map((b) => `${fa(b, 0)}٪`).join(" / ")} قبلاً اعمال شده‌اند؛
            سامانه باید <span className="font-mono">tmin</span> و <span className="font-mono">tmax</span>{" "}
            هر روز را بخواند.
            {hours.provenance !== "spec" && (
              <span className="text-warn"> ⚠️ منشأ: {PROVENANCE_LABEL[hours.provenance]}</span>
            )}
          </p>
        </div>

        {/* ── §۲۶ فیلتر + ماشین‌حساب ── */}
        <div className="rounded-xl bg-soft/60 p-3">
          <div className="mb-2 flex items-center gap-2">
            <ShieldCheck className="size-3.5 text-primary-500" />
            <span className="text-xs font-black text-ink">فیلتر ارزش معامله</span>
            <span
              data-testid="spec-filter-thresholds"
              className="rounded-md bg-card px-1.5 py-0.5 text-[10px] text-ink-3"
            >
              سود خالص ≥ {fa(filter.min_net_profit_pct, 0)}٪ · RR ≥ {fa(filter.min_risk_reward, 0)}
            </span>
          </div>

          <div className="grid grid-cols-4 gap-1.5">
            {(
              [
                ["ورود", entry, setEntry],
                ["هدف", target, setTarget],
                ["حد ضرر", stop, setStop],
                ["هزینه٪", cost, setCost],
              ] as const
            ).map(([label, value, setter]) => (
              <label key={label} className="block">
                <span className="block text-[10px] text-ink-3">{label}</span>
                <input
                  value={value}
                  onChange={(e) => setter(e.target.value)}
                  inputMode="decimal"
                  dir="ltr"
                  className="mt-0.5 w-full rounded-lg border border-line bg-card px-2 py-1.5 font-mono text-xs text-ink"
                />
              </label>
            ))}
          </div>

          <label className="mt-1.5 block">
            <span className="block text-[10px] text-ink-3">
              احتمال موفقیت p (٪) — خالی بگذارید اگر بک‌تست معتبر نیست
            </span>
            <input
              value={probability}
              onChange={(e) => setProbability(e.target.value)}
              inputMode="decimal"
              dir="ltr"
              placeholder="مثلاً 60"
              className="mt-0.5 w-full rounded-lg border border-line bg-card px-2 py-1.5 font-mono text-xs text-ink"
            />
          </label>

          <div className="mt-2 grid grid-cols-2 gap-1.5 text-[11px] sm:grid-cols-4">
            {[
              ["سود خالص W", evaluation.netProfitPct],
              ["ریسک خالص L", evaluation.netRiskPct],
              ["RR", evaluation.riskReward],
              ["EV", evaluation.expectedValuePct],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-lg bg-card px-2 py-1.5">
                <div className="text-[10px] text-ink-3">{label as string}</div>
                <b className="font-mono text-xs text-ink" dir="ltr">
                  {fa(value as number | null)}
                </b>
              </div>
            ))}
          </div>

          <div
            data-testid="spec-trade-verdict"
            className={`mt-2 rounded-lg px-2.5 py-1.5 text-[11px] font-bold ${verdict.cls}`}
          >
            {verdict.label}
          </div>

          {evaluation.reasons.length > 0 && (
            <ul className="mt-1.5 space-y-0.5 text-[10px] text-ink-3">
              {evaluation.reasons.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          )}

          <p className="mt-2 text-[10px] leading-relaxed text-ink-3">
            {fee == null ? (
              <>تعرفهٔ {defaultFeeKind}: «ناموجود در پاسخ API»</>
            ) : (
              <>
                تعرفهٔ {fee.label_fa}:{" "}
                {fee.fee_per_side == null
                  ? "«ناموجود»"
                  : `${fa(fee.fee_per_side * 100)}٪ هر سمت`}
                {fee.round_trip_fee_per_side != null &&
                  ` (رفت‌وبرگشت ${fa(fee.round_trip_fee_per_side * 100)}٪)`}
                {fee.provenance !== "spec" && (
                  <span className={fee.provenance === "unavailable" ? "text-down" : "text-warn"}>
                    {" "}
                    — منشأ: {PROVENANCE_LABEL[fee.provenance]}
                  </span>
                )}
              </>
            )}
          </p>
          <p className="mt-1 text-[10px] text-ink-3">
            حداقل حرکت ناخالص لازم = {fa(filter.min_net_profit_pct, 0)}٪ سود خالص +{" "}
            {tripPct == null ? "هزینهٔ نامعلوم" : `${fa(tripPct)}٪ کارمزد`} ={" "}
            <b className="font-mono" dir="ltr">
              {requiredMove == null ? "—" : `${fa(requiredMove)}٪`}
            </b>{" "}
            پیش از اسپرد و لغزش (§۲۰ و §۲۷.۱).
          </p>
        </div>
      </div>

      <div className="mt-3 space-y-1 border-t border-line pt-3 text-[10px] leading-relaxed text-ink-3">
        <p>{PHYSICAL_DELIVERY_NOTE}</p>
        <p>{DISCLAIMER}</p>
      </div>
    </div>
  );
}

/**
 * پوستهٔ بارگذاری/خطا برای صفحه‌های طلا و نقره.
 *
 * تا وقتی قواعد معتبر نرسیده، هیچ عددی نمایش داده نمی‌شود و در صورت خطا پیام صریح
 * می‌آید؛ چون نشان‌دادن آستانه یا تعرفهٔ ساختگی بدتر از نشان‌ندادن است (§۱۳ و §۲۸.۲).
 */
export function AssistantRulesPanel({
  defaultFeeKind = "commodity_fund",
  className = "",
}: {
  defaultFeeKind?: InstrumentKind;
  className?: string;
}) {
  const { rules, isLoading, error } = useAssistantRules();

  if (isLoading) {
    return (
      <div
        data-testid="spec-rules-loading"
        className={`flex items-center gap-2 rounded-2xl border border-line bg-card p-4 text-[11px] text-ink-3 shadow-[var(--shadow-card)] ${className}`}
      >
        <Loader2 className="size-4 animate-spin text-primary-500" />
        در حال خواندن قواعد بازار و فیلتر ارزش معامله…
      </div>
    );
  }

  if (!rules) {
    return (
      <div
        data-testid="spec-rules-unavailable"
        className={`rounded-2xl border border-down/40 bg-down/10 p-4 text-[11px] text-down shadow-[var(--shadow-card)] ${className}`}
      >
        <div className="flex items-center gap-2 font-bold">
          <AlertTriangle className="size-4" />
          قواعد بازار و فیلتر ارزش معامله در دسترس نیست
        </div>
        <p className="mt-1 leading-relaxed">
          {error ?? "پاسخ API معتبر نبود."} — تا دریافت قواعد، هیچ آستانه یا تعرفه‌ای نمایش داده
          نمی‌شود؛ عدد ساختگی به‌جای عدد سند گذاشته نمی‌شود (§۱۳ و §۲۸.۲).
        </p>
      </div>
    );
  }

  return <SpecRulesCard rules={rules} defaultFeeKind={defaultFeeKind} className={className} />;
}
