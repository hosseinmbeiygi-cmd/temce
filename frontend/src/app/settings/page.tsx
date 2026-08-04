"use client";

import { useState } from "react";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { toast } from "sonner";

export default function SettingsPage() {
  const [theme, setTheme] = useState("dark");
  const [lang, setLang] = useState("fa");
  const [refreshInterval, setRefreshInterval] = useState("30");
  const [apiEndpoint, setApiEndpoint] = useState("http://localhost:8000/api/v1");
  const [notifications, setNotifications] = useState({
    email: true,
    console: true,
    sound: false,
  });

  const handleSave = () => {
    toast.success("تنظیمات با موفقیت ذخیره شد");
  };

  return (
    <AppLayout title="تنظیمات" subtitle="تنظیمات سامانه">
      <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 800 }}>
        <Card title="امنیت حساب" subtitle="احراز هویت دومرحله‌ای و تنظیمات امنیتی">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-surface-400 leading-relaxed">
              با فعال‌سازی MFA، ورود به حساب شما با یک کد یک‌بارمصرف اضافی محافظت می‌شود.
            </p>
            <Link
              href="/settings/security"
              className="shrink-0 px-4 py-2.5 rounded-xl bg-primary-600 text-white text-sm font-semibold hover:bg-primary-500 transition-colors"
            >
              مدیریت MFA
            </Link>
          </div>
        </Card>

        <Card title="عمومی">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label className="setting-label" style={{ display: "block", marginBottom: 6, fontSize: 13, color: "var(--text-secondary)" }}>پوسته</label>
              <select value={theme} onChange={e => setTheme(e.target.value)} className="select">
                <option value="dark">تیره</option>
                <option value="light">روشن</option>
                <option value="system">هماهنگ با سیستم</option>
              </select>
            </div>
            <div>
              <label className="setting-label" style={{ display: "block", marginBottom: 6, fontSize: 13, color: "var(--text-secondary)" }}>زبان</label>
              <select value={lang} onChange={e => setLang(e.target.value)} className="select">
                <option value="fa">فارسی</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>
        </Card>

        <Card title="API">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label className="setting-label" style={{ display: "block", marginBottom: 6, fontSize: 13, color: "var(--text-secondary)" }}>آدرس API</label>
              <input type="text" value={apiEndpoint} onChange={e => setApiEndpoint(e.target.value)}
                className="select" style={{ width: "100%", fontFamily: "'Inter', monospace" }} />
            </div>
            <div>
              <label className="setting-label" style={{ display: "block", marginBottom: 6, fontSize: 13, color: "var(--text-secondary)" }}>فاصله به‌روزرسانی (ثانیه)</label>
              <input type="number" value={refreshInterval} onChange={e => setRefreshInterval(e.target.value)}
                className="select" style={{ width: "100%" }} />
            </div>
          </div>
        </Card>

        <Card title="اعلان‌ها">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[
              { id: "email", label: "اعلان از طریق ایمیل" },
              { id: "console", label: "نمایش در کنسول" },
              { id: "sound", label: "صدای هشدار" },
            ].map((item) => (
              <label key={item.id} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                <input
                  type="checkbox"                    checked={notifications[item.id as keyof typeof notifications]}
                    onChange={() => setNotifications((prev) => ({ ...prev, [item.id]: !prev[item.id as keyof typeof notifications] }))}
                  style={{ width: 16, height: 16, accentColor: "var(--accent-primary)" }}
                />
                <span style={{ fontSize: 13, color: "var(--text-primary)" }}>{item.label}</span>
              </label>
            ))}
          </div>
        </Card>

        <div>
          <button onClick={handleSave}
            style={{
              padding: "10px 24px",
              background: "var(--accent-primary)",
              color: "white",
              border: "none",
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              transition: "opacity 0.2s",
            }}
            onMouseOver={e => (e.currentTarget.style.opacity = "0.9")}
            onMouseOut={e => (e.currentTarget.style.opacity = "1")}
          >
            ذخیره تنظیمات
          </button>
        </div>
      </div>
    </AppLayout>
  );
}
