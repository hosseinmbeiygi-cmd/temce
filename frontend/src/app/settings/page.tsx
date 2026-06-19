"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";

export default function SettingsPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState("dark");
  const [lang, setLang] = useState("fa");
  const [refreshInterval, setRefreshInterval] = useState("30");
  const [apiEndpoint, setApiEndpoint] = useState("http://localhost:8000/api/v1");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-surface-100">تنظیمات</h1>
          <p className="text-sm text-surface-500 mt-1">تنظیمات سامانه</p>
        </div>

        {saved && (
          <div className="bg-accent-emerald/10 border border-accent-emerald/30 text-accent-emerald px-4 py-2 rounded-lg mb-4 text-sm">تنظیمات ذخیره شد</div>
        )}

        <div className="space-y-4">
          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-4">عمومی</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-surface-400 mb-1">پوسته</label>
                <select value={theme} onChange={(e) => setTheme(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-surface-200">
                  <option value="dark">تیره</option>
                  <option value="light">روشن</option>
                  <option value="system">هماهنگ با سیستم</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-surface-400 mb-1">زبان</label>
                <select value={lang} onChange={(e) => setLang(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-surface-200">
                  <option value="fa">فارسی</option>
                  <option value="en">English</option>
                </select>
              </div>
            </div>
          </div>

          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-4">API</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-surface-400 mb-1">آدرس API</label>
                <input type="text" value={apiEndpoint} onChange={(e) => setApiEndpoint(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-surface-200 font-mono text-sm" />
              </div>
              <div>
                <label className="block text-sm text-surface-400 mb-1">فاصله به‌روزرسانی (ثانیه)</label>
                <input type="number" value={refreshInterval} onChange={(e) => setRefreshInterval(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-surface-200" />
              </div>
            </div>
          </div>

          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-4">اعلان‌ها</h2>
            <div className="space-y-3">
              {[
                { id: "email", label: "اعلان از طریق ایمیل" },
                { id: "console", label: "نمایش در کنسول" },
                { id: "sound", label: "صدای هشدار" },
              ].map((item) => (
                <label key={item.id} className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" defaultChecked className="w-4 h-4 accent-primary-500" />
                  <span className="text-sm text-surface-300">{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button onClick={handleSave}
            className="px-6 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm font-medium transition-all">
            ذخیره تنظیمات
          </button>
        </div>
      </main>
    </div>
  );
}
