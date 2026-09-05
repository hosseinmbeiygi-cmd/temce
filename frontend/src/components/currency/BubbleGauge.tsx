"use client";

import { cn } from "@/lib/cn";

/** نیم‌دایرهٔ حباب دلار: <30 سبز، 30-100 کهربایی، >100 قرمز (آستانه‌ها از پرامپت). */
export function BubbleGauge({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(value, 200));
  const angle = (clamped / 200) * 180; // 0..200% → 0..180°
  const tone =
    value < 30
      ? { text: "text-emerald-500", bar: "bg-emerald-500", label: "نسبتاً پایدار" }
      : value <= 100
        ? { text: "text-amber-500", bar: "bg-amber-500", label: "فشار متوسط" }
        : { text: "text-rose-500", bar: "bg-rose-500", label: value > 150 ? "ریسک بحرانی" : "ریسک بسیار بالا" };

  return (
    <div className="flex flex-col items-center gap-2 py-2">
      <div className={cn("text-3xl font-extrabold tabular-nums", tone.text)}>
        {value.toFixed(1)}٪
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div
          className={cn("h-full rounded-full transition-all duration-500", tone.bar)}
          style={{ width: `${(angle / 180) * 100}%` }}
        />
      </div>
      <div className="flex w-full justify-between text-[10px] opacity-60">
        <span>۰٪</span>
        <span>۱۰۰٪</span>
        <span>۲۰۰٪</span>
      </div>
      <div className={cn("text-xs font-medium", tone.text)}>{tone.label}</div>
    </div>
  );
}
