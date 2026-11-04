"use client";

import { Coins, Sun, Monitor, Factory, TrendingDown, AlertTriangle } from "lucide-react";

export default function FundamentalCard() {
  const drivers = [
    { icon: Sun, label: "خورشیدی", tone: "text-up", text: "تقاضا در صنعت خورشیدی و فولاد خورشیدی حساس به نقره" },
    { icon: Monitor, label: "الکترونیک/نیمه‌رسانا", tone: "text-up", text: "استفاده در مقاوم‌تر، الکترونیک و اتصالات عایق" },
    { icon: Factory, label: "عایق و جوش", tone: "text-up", text: "عایق الکتریکی و جوش — استفاده صنعتی کلاسیک" },
    { icon: TrendingDown, label: "ارزش‌نگهداری", tone: "text-warn", text: "نقره به عنوان ذخیره ارزش در دوره‌های تورمی احتمالاً محبوب‌تر باشد" },
    { icon: AlertTriangle, label: "عرضه و تقاضا", tone: "text-ink-2", text: "تغییر عرضه حفره‌ای + بازیافت + تقاضای صنعتی تعیین نرخ" },
  ];

  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="mb-4 flex items-center gap-2">
        <Coins className="size-4 text-primary-500" />
        <h3 className="text-sm font-black text-ink">خلاصه فاندامنتال بازار نقره</h3>
        <span className="text-[10px] text-ink-3">منبع: راهنمای Silver Institute و داده‌های تقاضای صنعتی</span>
      </div>

      <ul className="grid gap-2 text-xs">
        {drivers.map((d) => (
          <li key={d.label} className="rounded-xl bg-soft/40 px-3 py-2 flex items-start gap-3">
            <span className={`mt-0.5 size-4 shrink-0 ${d.tone}`}><d.icon className="size-4" /></span>
            <div>
              <span className="font-bold text-ink">{d.label}:</span>
              {" "}
              <span className="text-ink-3">{d.text}</span>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-3 rounded-xl border border-line bg-soft/30 px-3 py-2 text-[11px] text-ink-3">
        <span className="font-bold text-ink-2">تغییر عرضه:</span>
        {" "}
        عرضه حفره‌ای نقره در سال ۲۰۲۳ حدود ۴۹.۸۴ میلیون آونس جهانی (وزن تقریبی) با کاهش درصدی نسبت به سال پیش؛ تقاضای صنعتی در سال‌های اخیر در بخش خورشیدی و الکترونیک رشد چشم‌گیر.
      </div>
    </div>
  );
}
