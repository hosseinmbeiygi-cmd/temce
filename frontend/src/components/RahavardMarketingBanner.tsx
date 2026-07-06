"use client";

import { useState } from "react";

const SECTIONS = [
  {
    id: "overview",
    title: "نمای کلی امکانات",
    icon: "dashboard",
    items: [
      "امکان دریافت گزارش‌ها به تفکیک فصل و ماه",
      "امکان دریافت گزارش‌ها به تفکیک نوع فروش",
      "تغییر واحد پولی به یورو، تتر و ...",
      "نمایش داده‌های تجمیعی آخرین گزارش سال مالی جاری و گزارش‌های مشابه تاریخی",
      "اضافه شدن فیلترهای متنوع: سالانه (مجمع)، TTM (۱۲ماهه اخیر)، MRQ فصلی و میان‌دوره‌ای",
      "دریافت صورت‌های مالی بر اساس واحد‌های پولی متنوع (دلار، یورو، تتر و...)",
      "اضافه شدن ۴ مدل نحوه نمایش (عددی، درصدی، مقایسه‌ای و براساس دارایی)",
      "امکان مقایسه بهتر و راحت‌تر صورت‌های مالی",
      "گزارش نمای صنعت و نمای شرکت‌های صنعت",
      "امکان انتخاب اعداد به زبان‌های فارسی و انگلیسی",
      "نمایش چارت روند هر ردیف از صورت‌های مالی",
      "امکان خروجی گرفتن از جدول‌ها به دو صورت فایل اکسل و CSV",
    ],
  },
  {
    id: "production",
    title: "گزارشات تولید و فروش",
    icon: "precision_manufacturing",
    content:
      "در بخش تولید و فروش می‌توانید گزارشات را به تفکیک اطلاعات تولید و فروش، تخفیف و برگشت فروش و انرژی مصرفی مشاهده کنید.",
    filters: ["تاریخ گزارش", "نوع گزارش", "واحد پول", "نوع فروش", "نحوه نمایش"],
    reportTypes: [
      "سالانه (۱۲ ماهه تجمعی)",
      "ماهانه تجمعی",
      "ماهانه به تفکیک ماه",
      "فصلی تجمعی (۳، ۶، ۹ و ۱۲ ماهه)",
      "فصلی به تفکیک فصل",
    ],
    saleTypes: ["مجموع", "داخلی", "صادراتی", "فروش"],
    outputs: ["مقدار تولید", "مقادیر فروش", "مبلغ فروش", "نرخ فروش", "نسبت فروش به کل", "درآمد حاصل از ارائه خدمات"],
  },
  {
    id: "filters",
    title: "فیلترها و تنظیمات",
    icon: "tune",
    items: [
      "تاریخ: تعیین بازه انتشار گزارش",
      "نوع گزارش: سالانه (مجمع) یا میان‌دوره‌ای",
      "واحد پول: ریال، دلار، یورو و تتر (طلایی)",
      "نحوه نمایش: عادی، درصد از دارایی، نرخ رشد و مقایسه‌ای (طلایی)",
    ],
  },
  {
    id: "ttm",
    title: "TTM و MRQ",
    icon: "schedule",
    items: [
      "سالانه (مجمع): آخرین گزارش ۱۲ ماهه مرتبط با سال‌های مالی",
      "TTM (دوازده ماه گذشته): عملکرد مالی شرکت در ۱۲ ماه گذشته",
      "MRQ (آخرین فصل مالی): گزارش مالی آخرین سه‌ماهه منتشر شده",
      "میان‌دوره‌ای: گزارش‌های فصلی با فیلترهای اصلی/تلفیقی، حسابرسی شده/نشده، تجدید ارائه شده/نشده",
    ],
  },
];

export default function RahavardMarketingBanner() {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="glass-card p-5 mb-6" style={{ borderRight: "3px solid var(--accent-primary)" }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <span className="material-icons text-3xl" style={{ color: "var(--accent-primary)" }}>
          school
        </span>
        <div>
          <h2 className="text-lg font-bold" style={{ color: "var(--text-primary-light)" }}>
            بخش بنیادی ره‌آورد
          </h2>
          <p className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
            آخرین بروزرسانی: به‌روزرسانی‌های اخیر بخش بنیادی سایت ره‌آورد
          </p>
        </div>
      </div>

      {/* Intro */}
      <p className="text-sm mb-4 leading-7" style={{ color: "var(--text-secondary-light)" }}>
        تحلیل بنیادی یکی از موثرترین و پرکاربردترین روش‌ها برای ارزیابی و انتخاب سهام در بازار بورس است.
        این روش به سرمایه‌گذاران کمک می‌کند تا با بررسی عوامل اقتصادی، مالی و مدیریتی، ارزش ذاتی یک سهم را تخمین بزنند.
      </p>

      {/* Access paths */}
      <div className="flex flex-wrap gap-2 mb-4">
        <span className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-full" style={{ background: "var(--bg-surface)", color: "var(--text-secondary-light)" }}>
          <span className="material-icons text-sm">visibility</span>
          صفحه در یک نگاه → بنیادی
        </span>
        <span className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-full" style={{ background: "var(--bg-surface)", color: "var(--text-secondary-light)" }}>
          <span className="material-icons text-sm">info</span>
          نوار اطلاعات نماد → بنیادی
        </span>
      </div>

      {/* Section tabs */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => setExpanded(expanded === s.id ? null : s.id)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg whitespace-nowrap transition-all"
            style={{
              background: expanded === s.id ? "var(--accent-primary)" : "var(--bg-surface)",
              color: expanded === s.id ? "#fff" : "var(--text-secondary-light)",
            }}
          >
            <span className="material-icons text-sm">{s.icon}</span>
            {s.title}
          </button>
        ))}
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="rounded-lg p-4" style={{ background: "var(--bg-surface)" }}>
          {(() => {
            const section = SECTIONS.find((s) => s.id === expanded);
            if (!section) return null;

            return (
              <div>
                <h3 className="text-sm font-bold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary-light)" }}>
                  <span className="material-icons text-base" style={{ color: "var(--accent-primary)" }}>{section.icon}</span>
                  {section.title}
                </h3>

                {section.content && (
                  <p className="text-xs mb-3 leading-6" style={{ color: "var(--text-secondary-light)" }}>
                    {section.content}
                  </p>
                )}

                {section.items && (
                  <ul className="space-y-1.5">
                    {section.items.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs" style={{ color: "var(--text-secondary-light)" }}>
                        <span className="material-icons text-xs mt-0.5" style={{ color: "var(--accent-secondary)" }}>check_circle</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                )}

                {section.filters && (
                  <div className="mt-3">
                    <span className="text-xs font-bold" style={{ color: "var(--text-primary-light)" }}>فیلترها: </span>
                    <span className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
                      {section.filters.join(" · ")}
                    </span>
                  </div>
                )}

                {section.reportTypes && (
                  <div className="mt-3">
                    <span className="text-xs font-bold" style={{ color: "var(--text-primary-light)" }}>انواع گزارش: </span>
                    <span className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
                      {section.reportTypes.join(" · ")}
                    </span>
                  </div>
                )}

                {section.saleTypes && (
                  <div className="mt-3">
                    <span className="text-xs font-bold" style={{ color: "var(--text-primary-light)" }}>نوع فروش: </span>
                    <span className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
                      {section.saleTypes.join(" · ")}
                    </span>
                  </div>
                )}

                {section.outputs && (
                  <div className="mt-3">
                    <span className="text-xs font-bold" style={{ color: "var(--text-primary-light)" }}>خروجی‌ها: </span>
                    <span className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
                      {section.outputs.join(" · ")}
                    </span>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
