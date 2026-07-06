"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface EcoEvent {
  id: string;
  date: string;
  time: string;
  title: string;
  country: string;
  category: string;
  importance: number;
  forecast: string;
  previous: string;
  analysis?: string;
}

interface CalendarResponse {
  events: EcoEvent[];
  grouped: Record<string, EcoEvent[]>;
  date_counts: Record<string, number>;
  total: number;
  categories: string[];
  date_range: { start: string; end: string };
}

interface Subscription {
  id: string;
  name: string;
  channel: string;
  email: string | null;
  telegram_id: string | null;
  min_importance: number;
  categories: string[];
  created_at: string;
  enabled: boolean;
}

interface SubscriptionForm {
  name: string;
  channel: string;
  email: string;
  telegram_id: string;
  min_importance: number;
  categories: string[];
}

// ── Helpers ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const IMPORTANCE_CONFIG: Record<number, { label: string; color: string; bg: string; stars: string }> = {
  3: { label: "بالا", color: "text-accent-rose", bg: "bg-accent-rose/10 border-accent-rose/30", stars: "⭐⭐⭐" },
  2: { label: "متوسط", color: "text-accent-amber", bg: "bg-accent-amber/10 border-accent-amber/20", stars: "⭐⭐" },
  1: { label: "پایین", color: "text-surface-400", bg: "bg-surface-800/50 border-surface-700/30", stars: "⭐" },
};

function formatDate(d: string): { day: string; weekday: string; month: string; full: string } {
  try {
    const dt = new Date(d + "T12:00:00");
    const weekdays = ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه"];
    const months = ["ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن", "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"];
    return {
      day: String(dt.getDate()).padStart(2, "0"),
      weekday: weekdays[dt.getDay()],
      month: months[dt.getMonth()],
      full: `${weekdays[dt.getDay()]} ${dt.getDate()} ${months[dt.getMonth()]} ${dt.getFullYear()}`,
    };
  } catch {
    return { day: d.slice(8), weekday: "", month: "", full: d };
  }
}

function isToday(d: string): boolean {
  try {
    return d === new Date().toISOString().slice(0, 10);
  } catch {
    return false;
  }
}

const ALL_CATEGORIES = "همه دسته‌ها";

// ── Main Page ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function EconomicCalendarPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>(ALL_CATEGORIES);
  const [minImportance, setMinImportance] = useState<number>(1);
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null);
  const [showSubscribeModal, setShowSubscribeModal] = useState(false);
  const [showSubsModal, setShowSubsModal] = useState(false);
  const [subForm, setSubForm] = useState<SubscriptionForm>({
    name: "",
    channel: "email",
    email: "",
    telegram_id: "",
    min_importance: 3,
    categories: [],
  });
  const today = new Date().toISOString().slice(0, 10);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["economic-calendar", selectedCategory, minImportance],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("min_importance", String(minImportance));
      if (selectedCategory !== ALL_CATEGORIES) params.set("category", selectedCategory);
      const res = await apiGet<{ success: boolean; data: CalendarResponse }>(
        `/economic-calendar?${params.toString()}`
      );
      return res.data;
    },
    refetchInterval: 120_000,
  });

  const events = data?.events || [];
  const categories = data?.categories || [];
  const grouped = data?.grouped || {};
  const dates = useMemo(() => {
    const d = Object.keys(grouped).sort();
    const todayIdx = d.findIndex((dt) => dt === today);
    if (todayIdx > 2) return d.slice(todayIdx - 2, todayIdx + 10);
    return d.slice(0, 14);
  }, [grouped, today]);

  return (
    <AppLayout title="📅 تقویم اقتصادی" subtitle="رویدادهای مهم بازار سرمایه ایران و جهان">
      <div className="max-w-5xl mx-auto space-y-5">
        {/* ── Summary Stats ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="glass-card p-3 text-center">
            <p className="text-2xl font-bold text-surface-100">{data?.total || 0}</p>
            <p className="text-xs text-surface-500">رویداد</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-2xl font-bold text-accent-rose">
              {events.filter((e) => e.importance === 3).length}
            </p>
            <p className="text-xs text-surface-500">اهمیت بالا</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-2xl font-bold text-accent-amber">
              {events.filter((e) => e.importance === 2).length}
            </p>
            <p className="text-xs text-surface-500">اهمیت متوسط</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-2xl font-bold text-accent-emerald">{dates.length}</p>
            <p className="text-xs text-surface-500">روز</p>
          </div>
        </div>

        {/* ── Filters ── */}
        <div className="flex flex-wrap gap-3 items-center">
          {/* Category filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-xs text-surface-300 outline-none focus:border-primary-500"
          >
            <option value={ALL_CATEGORIES}>همه دسته‌ها ({categories.length})</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>

          {/* Importance filter */}
          <div className="flex gap-1">
            {[1, 2, 3].map((imp) => (
              <button
                key={imp}
                onClick={() => setMinImportance(minImportance === imp ? 1 : imp)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  minImportance === imp
                    ? "bg-primary-600 text-white"
                    : "bg-surface-800 text-surface-500 hover:text-surface-300"
                }`}
              >
                {imp === 1 ? "⭐" : imp === 2 ? "⭐⭐" : "⭐⭐⭐"}
              </button>
            ))}
          </div>

          {/* Subscription buttons */}
          <button
            onClick={() => setShowSubsModal(true)}
            className="px-2.5 py-1.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-lg text-xs transition-colors"
          >
            🔔 اشتراک‌ها
          </button>
          <button
            onClick={() => setShowSubscribeModal(true)}
            className="px-3 py-1.5 bg-primary-700 hover:bg-primary-600 text-white rounded-lg text-xs font-medium transition-colors"
          >
            ➕ اشتراک رویدادها
          </button>

          <button
            onClick={() => refetch()}
            className="px-2.5 py-1.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-lg text-xs transition-colors"
          >
            🔄 تازه‌سازی
          </button>
        </div>

        {/* ── Calendar ── */}
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
          </div>
        ) : isError ? (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-surface-400">خطا در دریافت تقویم اقتصادی</p>
            <button onClick={() => refetch()} className="mt-3 px-4 py-2 bg-primary-600 rounded-lg text-sm text-white">
              تلاش مجدد
            </button>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">📅</p>
            <p className="text-surface-500">رویدادی برای نمایش وجود ندارد</p>
          </div>
        ) : (
          <div className="space-y-4">
            {dates.map((d) => {
              const dayEvents = grouped[d] || [];
              const fmt = formatDate(d);
              const todayFlag = isToday(d);
              return (
                <div key={d}>
                  {/* Date Header */}
                  <div className={`flex items-center gap-3 mb-2 px-1 ${
                    todayFlag ? "sticky top-0 z-10 bg-surface-900/95 backdrop-blur-sm py-2 -mx-1 px-3 rounded-xl" : ""
                  }`}>
                    <div className={`flex items-center justify-center w-10 h-10 rounded-xl font-bold text-sm ${
                      todayFlag ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-300"
                    }`}>
                      {fmt.day}
                    </div>
                    <div>
                      <p className={`text-sm font-semibold ${todayFlag ? "text-primary-300" : "text-surface-200"}`}>
                        {fmt.weekday} {fmt.day} {fmt.month}
                      </p>
                      <p className="text-[10px] text-surface-500">
                        {dayEvents.length} رویداد • {todayFlag && "امروز"}
                      </p>
                    </div>
                  </div>

                  {/* Events */}
                  <div className="space-y-1.5 mr-12">
                    {dayEvents.map((ev) => {
                      const imp = IMPORTANCE_CONFIG[ev.importance] || IMPORTANCE_CONFIG[1];
                      const isExpanded = expandedEvent === ev.id;
                      return (
                        <div key={ev.id}>
                          <div
                            onClick={() => setExpandedEvent(isExpanded ? null : ev.id)}
                            className={`glass-card p-3 border-r-2 ${imp.bg} hover:bg-surface-800/60 transition-colors cursor-pointer ${isExpanded ? "rounded-b-none" : ""}`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                {/* Title + Importance */}
                                <div className="flex items-center gap-2 mb-0.5">
                                  <span className="text-[10px]">{ev.country}</span>
                                  <span className="text-[10px] text-surface-600">•</span>
                                  <span className="text-[10px] text-surface-500">{ev.category}</span>
                                  <span className={`text-[10px] ${imp.color}`}>{imp.stars}</span>
                                </div>
                                <p className="text-sm font-semibold text-surface-200">{ev.title}</p>

                                {/* Forecast / Previous */}
                                {(ev.forecast || ev.previous) && (
                                  <div className="flex gap-3 mt-1.5">
                                    {ev.forecast && (
                                      <span className="text-[10px] text-surface-500">
                                        پیش‌بینی: <span className="font-mono text-surface-300">{ev.forecast}</span>
                                      </span>
                                    )}
                                    {ev.previous && (
                                      <span className="text-[10px] text-surface-500">
                                        قبلی: <span className="font-mono text-surface-300">{ev.previous}</span>
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>

                              <div className="shrink-0 flex flex-col items-end gap-1">
                                {/* Time */}
                                <p className="text-xs font-mono font-bold text-surface-300">
                                  {ev.time !== "—" ? ev.time : "⏰"}
                                </p>
                                {/* Expand indicator */}
                                {ev.analysis && (
                                  <span className="text-[10px] text-surface-600 transition-transform" style={{ transform: isExpanded ? "rotate(180deg)" : "none" }}>
                                    ▼
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Expanded Analysis */}
                          {isExpanded && ev.analysis && (
                            <div className="glass-card p-3 pt-2 border-t-0 border-r-2 rounded-t-none -mt-[1px] bg-surface-800/40" style={{ borderRightColor: "inherit", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                              <div className="flex gap-2">
                                <span className="text-primary-400 text-[10px] mt-0.5">📊</span>
                                <p className="text-[11px] text-surface-400 leading-relaxed">{ev.analysis}</p>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Info Footer ── */}
        <div className="glass-card p-4 text-xs text-surface-500 space-y-1">
          <p className="font-medium text-surface-400">ℹ️ درباره تقویم اقتصادی</p>
          <p>رویدادها بر اساس تقویم استاندارد بازارهای مالی تنظیم شده‌اند. تاریخ‌ها ممکن است تغییر کنند.</p>
          <div className="flex gap-4 mt-2">
            <span className="flex items-center gap-1"><span className="text-accent-rose">⭐⭐⭐</span> اهمیت بالا — تأثیر قابل توجه بر بازار</span>
            <span className="flex items-center gap-1"><span className="text-accent-amber">⭐⭐</span> اهمیت متوسط</span>
            <span className="flex items-center gap-1"><span className="text-surface-400">⭐</span> اهمیت پایین</span>
          </div>
        </div>
        {/* ── Subscribe Modal ── */}
        {showSubscribeModal && (
          <SubscribeModal
            form={subForm}
            setForm={setSubForm}
            onClose={() => setShowSubscribeModal(false)}
            categories={categories}
          />
        )}

        {/* ── Subscriptions List Modal ── */}
        {showSubsModal && (
          <SubscriptionsModal onClose={() => setShowSubsModal(false)} />
        )}
      </div>
    </AppLayout>
  );
}

// ── Subscribe Modal ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function SubscribeModal({
  form,
  setForm,
  onClose,
  categories,
}: {
  form: SubscriptionForm;
  setForm: (f: SubscriptionForm) => void;
  onClose: () => void;
  categories: string[];
}) {
  const queryClient = useQueryClient();
  const [localForm, setLocalForm] = useState<SubscriptionForm>(form);
  const [successMsg, setSuccessMsg] = useState("");

  const subscribeMutation = useMutation({
    mutationFn: async (data: SubscriptionForm) => {
      const body: Record<string, unknown> = {
        name: data.name || undefined,
        channel: data.channel,
        min_importance: data.min_importance,
        categories: data.categories,
      };
      if (data.email) body.email = data.email;
      if (data.telegram_id) body.telegram_id = data.telegram_id;
      return apiPost<{ success: boolean; data: Subscription }>("/economic-calendar/subscribe", body);
    },
    onSuccess: () => {
      setSuccessMsg("✅ اشتراک با موفقیت ایجاد شد");
      setForm({ name: "", channel: "email", email: "", telegram_id: "", min_importance: 3, categories: [] });
      setLocalForm({ name: "", channel: "email", email: "", telegram_id: "", min_importance: 3, categories: [] });
      queryClient.invalidateQueries({ queryKey: ["economic-subscriptions"] });
      setTimeout(() => onClose(), 1500);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg("");
    if (localForm.channel !== "telegram" && !localForm.email) {
      alert("لطفاً ایمیل خود را وارد کنید");
      return;
    }
    if (localForm.channel !== "email" && !localForm.telegram_id) {
      alert("لطفاً شناسه تلگرام خود را وارد کنید");
      return;
    }
    subscribeMutation.mutate(localForm);
  };

  const toggleCategory = (cat: string) => {
    setLocalForm((prev) => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter((c) => c !== cat)
        : [...prev.categories, cat],
    }));
  };

  const channel = localForm.channel;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-surface-200">🔔 اشتراک رویدادهای اقتصادی</h2>
            <button onClick={onClose} className="text-surface-500 hover:text-surface-300 text-lg">&times;</button>
          </div>

          {successMsg ? (
            <div className="text-center py-6">
              <p className="text-accent-emerald text-sm">{successMsg}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3">
              {/* Name */}
              <div>
                <label className="block text-[11px] text-surface-500 mb-1">نام اشتراک (اختیاری)</label>
                <input
                  type="text"
                  value={localForm.name}
                  onChange={(e) => setLocalForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="مثلاً: رویدادهای هفتگی"
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
                />
              </div>

              {/* Channel */}
              <div>
                <label className="block text-[11px] text-surface-500 mb-1">کانال اعلان</label>
                <div className="flex gap-2">
                  {[
                    { value: "email", label: "📧 ایمیل" },
                    { value: "telegram", label: "✈️ تلگرام" },
                    { value: "both", label: "📧 + ✈️" },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setLocalForm((p) => ({ ...p, channel: opt.value, email: opt.value === "telegram" ? "" : p.email, telegram_id: opt.value === "email" ? "" : p.telegram_id }))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        channel === opt.value
                          ? "bg-primary-600 text-white"
                          : "bg-surface-800 text-surface-500 hover:text-surface-300"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Email */}
              {channel !== "telegram" && (
                <div>
                  <label className="block text-[11px] text-surface-500 mb-1">ایمیل</label>
                  <input
                    type="email"
                    value={localForm.email}
                    onChange={(e) => setLocalForm((p) => ({ ...p, email: e.target.value }))}
                    placeholder="example@email.com"
                    className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
                  />
                </div>
              )}

              {/* Telegram */}
              {channel !== "email" && (
                <div>
                  <label className="block text-[11px] text-surface-500 mb-1">شناسه / Chat ID تلگرام</label>
                  <input
                    type="text"
                    value={localForm.telegram_id}
                    onChange={(e) => setLocalForm((p) => ({ ...p, telegram_id: e.target.value }))}
                    placeholder="1234567890"
                    className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
                  />
                </div>
              )}

              {/* Min Importance */}
              <div>
                <label className="block text-[11px] text-surface-500 mb-1">حداقل اهمیت</label>
                <div className="flex gap-2">
                  {[1, 2, 3].map((imp) => (
                    <button
                      key={imp}
                      type="button"
                      onClick={() => setLocalForm((p) => ({ ...p, min_importance: imp }))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        localForm.min_importance === imp
                          ? "bg-primary-600 text-white"
                          : "bg-surface-800 text-surface-500 hover:text-surface-300"
                      }`}
                    >
                      {imp === 1 ? "⭐" : imp === 2 ? "⭐⭐" : "⭐⭐⭐"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Categories */}
              <div>
                <label className="block text-[11px] text-surface-500 mb-1">
                  دسته‌بندی‌ها {localForm.categories.length > 0 && `(${localForm.categories.length})`}
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                  {categories.map((cat) => {
                    const active = localForm.categories.includes(cat);
                    return (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => toggleCategory(cat)}
                        className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                          active
                            ? "bg-primary-600/20 text-primary-300 border border-primary-600/30"
                            : "bg-surface-800 text-surface-500 border border-surface-700 hover:text-surface-300"
                        }`}
                      >
                        {active ? "✓ " : ""}{cat}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[9px] text-surface-600 mt-1">خالی = همه دسته‌بندی‌ها</p>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={subscribeMutation.isPending}
                className="w-full py-2.5 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-all"
              >
                {subscribeMutation.isPending ? "در حال ذخیره..." : "✅ فعال‌سازی اشتراک"}
              </button>

              {subscribeMutation.isError && (
                <p className="text-[10px] text-accent-rose text-center">
                  خطا در ایجاد اشتراک. لطفاً دوباره تلاش کنید.
                </p>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Subscriptions List Modal ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

function SubscriptionsModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();

  const { data: subs, isLoading, isError } = useQuery({
    queryKey: ["economic-subscriptions"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: Subscription[] }>("/economic-calendar/subscriptions");
      return res.data;
    },
    refetchInterval: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      return apiDelete<{ success: boolean; data: { deleted: string } }>("/economic-calendar/subscriptions/" + id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["economic-subscriptions"] });
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-md mx-4 max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="glass-card p-5 flex flex-col max-h-full">
          <div className="flex items-center justify-between mb-3 shrink-0">
            <h2 className="text-base font-bold text-surface-200">🔔 اشتراک‌های فعال</h2>
            <button onClick={onClose} className="text-surface-500 hover:text-surface-300 text-lg">&times;</button>
          </div>

          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mx-auto" />
            </div>
          ) : isError ? (
            <div className="text-center py-8">
              <p className="text-xs text-accent-rose">خطا در دریافت اشتراک‌ها</p>
            </div>
          ) : !subs || subs.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-3xl mb-2">🔕</p>
              <p className="text-xs text-surface-500">هیچ اشتراک فعالی وجود ندارد</p>
              <p className="text-[10px] text-surface-600 mt-1">روی «➕ اشتراک رویدادها» کلیک کنید</p>
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto flex-1">
              {subs.map((sub) => (
                <div key={sub.id} className="bg-surface-800/50 rounded-lg p-3 border border-surface-700/30">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-surface-200 truncate">{sub.name}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                        <span className="text-[10px] text-surface-500">
                          {sub.channel === "email" ? "📧" : sub.channel === "telegram" ? "✈️" : "📧+✈️"} {sub.channel}
                        </span>
                        <span className="text-[10px] text-surface-500">
                          {IMPORTANCE_CONFIG[sub.min_importance]?.stars || "⭐"} حداقل
                        </span>
                        {sub.categories && sub.categories.length > 0 && (
                          <span className="text-[10px] text-surface-500">
                            {sub.categories.length} دسته
                          </span>
                        )}
                      </div>
                      {sub.email && <p className="text-[9px] text-surface-600 mt-0.5">📧 {sub.email}</p>}
                      {sub.telegram_id && <p className="text-[9px] text-surface-600 mt-0.5">✈️ {sub.telegram_id}</p>}
                    </div>
                    <button
                      onClick={() => { if (confirm("حذف اشتراک؟")) deleteMutation.mutate(sub.id); }}
                      disabled={deleteMutation.isPending}
                      className="shrink-0 text-surface-600 hover:text-accent-rose transition-colors text-xs"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
