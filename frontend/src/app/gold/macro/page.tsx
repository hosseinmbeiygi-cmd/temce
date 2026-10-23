"use client";

/**
 * Gold macro workspace.
 *
 * Shows what the API can actually serve: the live macro posture (latest stored
 * TIPS real yield, broad dollar index, gold trend) and the stored economic
 * calendar. CFTC COT positions and a DXY/TIPS history series are ingested into
 * the database but have no read endpoint yet, so they are reported as blocked
 * instead of being charted from synthetic values.
 */

import MacroPostureSection from "../components/MacroPostureSection";
import EventCalendarSection from "../components/EventCalendarSection";

const BLOCKED_CAPABILITIES = [
  {
    title: "موقعیت‌های CFTC (COT)",
    detail:
      "جدول gold_cot_positions با net managed-money و درصدک هفتگی پر می‌شود، اما هیچ اندپوینت GET برای خواندن آن وجود ندارد.",
    proof: "services/gold/features.py · models/gold_macro.py",
  },
  {
    title: "نمودار تاریخی بازده واقعی و DXY",
    detail:
      "اندپوینت macro/live فقط آخرین مشاهده را برمی‌گرداند؛ سری زمانی برای رسم نمودار در دسترس نیست، بنابراین درصدک DXY هم محاسبه نمی‌شود.",
    proof: "services/gold/macro_live.py",
  },
];

export default function GoldMacroPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h1 className="text-xl font-bold text-zinc-100">کلان طلا</h1>
        <p className="mt-1 text-xs text-zinc-500">
          بازده واقعی، شاخص دلار، روند طلا و تقویم رویدادهای پرنوسان
        </p>
      </div>

      <div className="rounded-2xl border p-4" style={{ borderColor: "var(--gd-border)" }}>
        <MacroPostureSection />
      </div>

      <div className="rounded-2xl border p-4" style={{ borderColor: "var(--gd-border)" }}>
        <EventCalendarSection />
      </div>

      <section className="space-y-2" data-testid="macro-blocked">
        <h2 className="text-sm font-semibold text-zinc-300">قابلیت‌های مسدود (بدون اندپوینت)</h2>
        <ul className="space-y-2">
          {BLOCKED_CAPABILITIES.map((item) => (
            <li
              key={item.title}
              className="rounded-xl border border-amber-800/40 bg-amber-950/20 p-3 text-xs text-amber-200"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{item.title}</span>
                <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold">
                  BLOCKED BY DATA
                </span>
              </div>
              <p className="mt-1 leading-5 text-amber-200/80">{item.detail}</p>
              <p className="mt-1 font-mono text-[10px] text-amber-200/50" dir="ltr">
                {item.proof}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
