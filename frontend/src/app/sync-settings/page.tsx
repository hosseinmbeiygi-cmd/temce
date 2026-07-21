"use client";

import { useState, useEffect, useCallback } from "react";
import AppLayout from "@/components/layout/AppLayout";
import {
  loadSyncSettings,
  saveSyncSettings,
  resetSyncSettings,
  DEFAULT_SYNC_SETTINGS,
  ALL_SECTION_KEYS,
  type SyncSettingsMap,
} from "@/lib/sync-settings";

// ── Slider helpers ────────────────────────────────────────────────────────────

const PRESET_VALUES = [1, 2, 5, 10, 15, 30, 60, 120, 240, 480];
const VALUE_LABELS: Record<number, string> = {
  1: "۱ دقیقه",
  2: "۲ دقیقه",
  5: "۵ دقیقه",
  10: "۱۰ دقیقه",
  15: "۱۵ دقیقه",
  30: "۳۰ دقیقه",
  60: "۱ ساعت",
  120: "۲ ساعت",
  240: "۴ ساعت",
  480: "۸ ساعت",
};

function nearestPreset(value: number): number {
  return PRESET_VALUES.reduce((prev, curr) =>
    Math.abs(curr - value) < Math.abs(prev - value) ? curr : prev,
  );
}

// ── Schema ────────────────────────────────────────────────────────────────────

interface SectionRowProps {
  sectionKey: string;
  setting: { label: string; icon: string; maxAgeMinutes: number };
  onChange: (key: string, value: number) => void;
  previewStatus: "ok" | "stale" | "outdated" | "—";
}

function SectionRow({ sectionKey, setting, onChange, previewStatus }: SectionRowProps) {
  const sliderIndex = PRESET_VALUES.indexOf(nearestPreset(setting.maxAgeMinutes));
  const currentIndex = sliderIndex >= 0 ? sliderIndex : 3; // default to 10 min

  const statusColors: Record<string, string> = {
    ok: "text-accent-emerald",
    stale: "text-accent-amber",
    outdated: "text-accent-rose",
    "—": "text-surface-500",
  };

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-surface-800/40 transition-colors">
      {/* Icon + Label */}
      <div className="flex items-center gap-2 w-40 shrink-0">
        <span className="text-lg">{setting.icon}</span>
        <span className="text-xs font-medium text-surface-300">{setting.label}</span>
      </div>

      {/* Slider */}
      <input
        type="range"
        min={0}
        max={PRESET_VALUES.length - 1}
        value={currentIndex}
        onChange={(e) => {
          const idx = parseInt(e.target.value, 10);
          onChange(sectionKey, PRESET_VALUES[idx]);
        }}
        className="flex-1 h-1.5 rounded-full appearance-none cursor-pointer
          bg-surface-700 accent-primary-500
          [&::-webkit-slider-thumb]:appearance-none
          [&::-webkit-slider-thumb]:w-3.5
          [&::-webkit-slider-thumb]:h-3.5
          [&::-webkit-slider-thumb]:rounded-full
          [&::-webkit-slider-thumb]:bg-primary-500
          [&::-webkit-slider-thumb]:shadow-lg
          [&::-webkit-slider-thumb]:shadow-primary-500/30"
      />

      {/* Value label */}
      <span className="w-20 text-center text-[11px] font-mono text-surface-400 shrink-0">
        {VALUE_LABELS[nearestPreset(setting.maxAgeMinutes)] || `${setting.maxAgeMinutes} دقیقه`}
      </span>

      {/* Preview status dot */}
      <div className="w-20 flex items-center justify-center gap-1.5 shrink-0">
        {previewStatus !== "—" && (
          <span
            className={`w-2 h-2 rounded-full ${
              previewStatus === "ok" ? "bg-accent-emerald" :
              previewStatus === "stale" ? "bg-accent-amber" :
              "bg-accent-rose"
            }`}
          />
        )}
        <span className={`text-[10px] font-semibold ${statusColors[previewStatus] || "text-surface-500"}`}>
          {previewStatus === "ok" ? "به‌روز" :
           previewStatus === "stale" ? "کمی قدیمی" :
           previewStatus === "outdated" ? "قدیمی" :
           "—"}
        </span>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SyncSettingsPage() {
  const [settings, setSettings] = useState<SyncSettingsMap>({ ...DEFAULT_SYNC_SETTINGS });
  const [saved, setSaved] = useState(false);
  const [resetConfirm, setResetConfirm] = useState(false);

  useEffect(() => {
    setSettings(loadSyncSettings());
  }, []);

  const handleChange = useCallback((key: string, value: number) => {
    setSettings((prev) => ({
      ...prev,
      [key]: { ...prev[key], maxAgeMinutes: value },
    }));
    setSaved(false);
  }, []);

  const handleSave = useCallback(() => {
    saveSyncSettings(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }, [settings]);

  const handleReset = useCallback(() => {
    resetSyncSettings();
    setSettings({ ...DEFAULT_SYNC_SETTINGS });
    setResetConfirm(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }, []);

  const hasChanges = ALL_SECTION_KEYS.some(
    (k) => settings[k]?.maxAgeMinutes !== DEFAULT_SYNC_SETTINGS[k]?.maxAgeMinutes,
  );

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto py-6 px-4" dir="rtl">
        {/* ── Header ── */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold text-surface-100">⚙️ تنظیمات Freshness</h1>
            <p className="text-xs text-surface-500 mt-1">
              آستانه زمانی هر بخش را تنظیم کنید. اگر داده‌ها از این محدوده قدیمی‌تر باشند،
              به‌عنوان «کمی قدیمی» (stale) یا «قدیمی» (outdated) علامت‌گذاری می‌شوند.
            </p>
          </div>
        </div>

        {/* ── Note ── */}
        <div className="mb-5 p-3 rounded-xl bg-primary-600/10 border border-primary-500/20 text-[11px] text-surface-400 leading-relaxed">
          <span className="font-bold text-primary-300">💡 راهنما:</span>
          <br />
          • مقدار تنظیمشده = حداکثر سن مجاز داده (دقیقه).
          <br />
          • اگر داده از این مقدار <strong>بیشتر</strong> ولی <strong>کمتر از ۳ برابر</strong> آن باشد →
          وضعیت <span className="text-accent-amber">«کمی قدیمی»</span>.
          <br />
          • اگر داده بیش از ۳ برابر مقدار تنظیمشده سن داشته باشد →
          وضعیت <span className="text-accent-rose">«قدیمی»</span>.
          <br />
          • تغییرات فقط در این مرورگر اعمال می‌شود (localStorage).
        </div>

        {/* ── Sections ── */}
        <div className="glass-card rounded-2xl p-4 border border-surface-700/50">
          {/* Column header */}
          <div className="flex items-center gap-3 px-3 pb-2 mb-1 border-b border-surface-700/30 text-[10px] text-surface-500">
            <span className="w-40">بخش</span>
            <span className="flex-1 text-center">آستانه</span>
            <span className="w-20 text-center">مقدار</span>
            <span className="w-20 text-center">پیش‌نمایش</span>
          </div>

          <div className="space-y-0.5">
            {ALL_SECTION_KEYS.map((key) => {
              const s = settings[key] || DEFAULT_SYNC_SETTINGS[key];
              // Preview: assume data is exactly at the threshold → "stale" boundary
              const previewMaxAge = s.maxAgeMinutes;
              // For preview, simulate data slightly over threshold to show "stale"
              const previewAge = previewMaxAge * 1.5;
              const previewStatus =
                previewAge <= previewMaxAge ? "ok" :
                previewAge <= previewMaxAge * 3 ? "stale" :
                "outdated";

              return (
                <SectionRow
                  key={key}
                  sectionKey={key}
                  setting={s}
                  onChange={handleChange}
                  previewStatus={previewStatus}
                />
              );
            })}
          </div>
        </div>

        {/* ── Actions ── */}
        <div className="flex items-center gap-3 mt-5">
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold
              bg-primary-600 text-white hover:bg-primary-500 transition-all
              shadow-lg shadow-primary-600/20 active:scale-95"
          >
            <span className="material-icons text-sm">{saved ? "check" : "save"}</span>
            {saved ? "ذخیره شد ✓" : "ذخیره تنظیمات"}
          </button>

          {hasChanges && (
            <span className="text-[10px] text-accent-amber">
              ⚠️ تغییرات ذخیره نشده
            </span>
          )}

          <div className="flex-1" />

          {resetConfirm ? (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-accent-rose">آیا مطمئن هستید؟</span>
              <button
                onClick={handleReset}
                className="px-3 py-2 rounded-lg text-[10px] font-bold bg-accent-rose/15 text-accent-rose
                  hover:bg-accent-rose/25 transition-all"
              >
                بله، ریست کن
              </button>
              <button
                onClick={() => setResetConfirm(false)}
                className="px-3 py-2 rounded-lg text-[10px] bg-surface-800 text-surface-400
                  hover:bg-surface-700 transition-all"
              >
                انصراف
              </button>
            </div>
          ) : (
            <button
              onClick={() => setResetConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[10px] text-surface-500
                hover:text-accent-rose hover:bg-accent-rose/10 transition-all"
            >
              <span className="material-icons text-sm">restart_alt</span>
              بازگشت به پیش‌فرض
            </button>
          )}
        </div>

        {/* ── Footer status ── */}
        <div className="mt-4 text-[9px] text-surface-600 text-center">
          داده‌ها در localStorage مرورگر شما ذخیره می‌شوند و فقط برای شما اعمال می‌شوند.
        </div>
      </div>
    </AppLayout>
  );
}
