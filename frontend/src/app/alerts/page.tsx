"use client";

import { useState, useEffect, FormEvent } from "react";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import SymbolSelector from "@/components/SymbolSelector";
import { apiGet, apiPost, apiPut, apiDelete, extractItems } from "@/lib/api";

interface Alert {
  id: string;
  instrument_id: string;
  symbol: string;
  alert_type: string;
  condition: Record<string, unknown>;
  channels: string[];
  enabled: boolean;
  triggered_count: number;
  last_triggered: string | null;
  description: string;
  created_at: string;
}

const ALERT_TYPES = [
  { value: "price_above", label: "قیمت بالاتر از" },
  { value: "price_below", label: "قیمت پایین‌تر از" },
  { value: "volume_above", label: "حجم بالاتر از" },
  { value: "rsi_oversold", label: "RSI اشباع فروش" },
  { value: "rsi_overbought", label: "RSI اشباع خرید" },
  { value: "cross_above_sma", label: "عبور از میانگین به بالا" },
  { value: "cross_below_sma", label: "عبور از میانگین به پایین" },
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [alertType, setAlertType] = useState("price_above");
  const [threshold, setThreshold] = useState("1000");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [historyAlertId, setHistoryAlertId] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<Array<{id: string; triggered_at: string; trigger_value: number; message: string}>>([]);
  const [manualEntry, setManualEntry] = useState(false);

  useEffect(() => {
    fetchAlerts();
  }, []);

  async function fetchAlerts() {
    try {
      const data = await apiGet<unknown>("/alerts?page_size=50");
      setAlerts(extractItems<Alert>(data));
    } catch (error) {
      console.error("Error fetching alerts:", error);
    }
    setLoading(false);
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError(""); setMessage("");
    if (!symbol) { setError("لطفاً یک نماد انتخاب کنید"); return; }
    try {
      const condition: Record<string, unknown> = { threshold: parseFloat(threshold), operator: "gte", field: "price" };
      if (alertType.includes("rsi")) condition.field = "rsi";
      if (alertType.includes("volume")) condition.field = "volume";
      if (alertType.includes("oversold")) { condition.field = "rsi"; condition.operator = "lte"; condition.threshold = 30; }
      if (alertType.includes("overbought")) { condition.field = "rsi"; condition.operator = "gte"; condition.threshold = 70; }
      // SMA cross alerts: the scheduler computes a boolean cross signal
      // (1.0 if crossed above/below SMA20 today, else 0.0).
      // NOTE: cross checks must run BEFORE the generic "below" → lte mapping.
      if (alertType === "cross_above_sma") { condition.field = "sma_cross_above"; condition.operator = "eq"; condition.threshold = 1; }
      if (alertType === "cross_below_sma") { condition.field = "sma_cross_below"; condition.operator = "eq"; condition.threshold = 1; }
      // Generic price_below → lte (after cross handling, since "cross_below_sma" also contains "below").
      if (alertType.includes("below") && !alertType.startsWith("cross_")) condition.operator = "lte";
      // Anti-spam: don't re-trigger the same alert within 30 minutes.
      condition.cooldown_minutes = 30;

      await apiPost("/alerts", {
        // instrument_id is a UUID (resolved server-side when available) —
        // never send the ticker symbol there. Leave it empty so the schema
        // default ("") applies and alerts are matched by symbol.
        symbol,
        alert_type: alertType,
        condition,
        channels: ["telegram", "console"],
        description,
      });
      setMessage("هشدار با موفقیت ایجاد شد");
      setShowForm(false);
      setThreshold("1000");
      setDescription("");
      fetchAlerts();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }

  async function toggleAlert(alert: Alert) {
    try {
      await apiPut(`/alerts/${alert.id}`, { enabled: !alert.enabled });
      fetchAlerts();
    } catch {}
  }

  async function deleteAlert(id: string) {
    try {
      await apiDelete(`/alerts/${id}`);
      fetchAlerts();
    } catch {}
  }

  async function fetchHistory(alertId: string) {
    if (historyAlertId === alertId) { setHistoryAlertId(null); return; }
    try {
      const data = await apiGet<{ success: boolean; data: { items: Array<{id: string; triggered_at: string; trigger_value: number; message: string}> } }>(`/alerts/${alertId}/history?page_size=10`);
      setHistoryData(data?.data?.items ?? []);
      setHistoryAlertId(alertId);
    } catch { setHistoryData([]); setHistoryAlertId(alertId); }
  }

  return (
    <AppLayout title="هشدارها">
        <div className="flex items-center justify-between mb-6">
          <button onClick={() => setShowForm(!showForm)} className="bg-primary-600 hover:bg-primary-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition">
            {showForm ? "بستن" : "هشدار جدید"}
          </button>
        </div>

        {message && <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-4 py-2 rounded-lg mb-4 text-sm">{message}</div>}
        {error && <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 px-4 py-2 rounded-lg mb-4 text-sm">{error}</div>}

        {showForm && (
          <div className="glass-card p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">هشدار جدید</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">نماد</label>
                  <div className="flex items-start gap-2">
                    <div className="flex-1">
                      {manualEntry ? (
                        /* ورود دستی: هر نمادی (حتی نمادهای جدید خارج از کاتالوگ) */
                        <input
                          type="text"
                          value={symbol}
                          onChange={(e) => setSymbol(e.target.value)}
                          placeholder="تایپ دستی نماد..."
                          className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white font-mono placeholder-gray-500"
                        />
                      ) : (
                        /* جستجو روی کل کاتالوگ (سهام/صندوق/طلا/ارز/رمزارز/کامودیتی) */
                        <SymbolSelector value={symbol} onChange={setSymbol} placeholder="انتخاب نماد..." />
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => setManualEntry((v) => !v)}
                      className="text-xs px-2 py-2 rounded-lg bg-surface-800 border border-surface-700 text-gray-400 hover:text-white whitespace-nowrap transition-colors"
                      title={manualEntry ? "جستجو از کاتالوگ نمادها" : "تایپ دستی هر نمادی"}
                    >
                      {manualEntry ? "🔍 جستجو" : "⌨️ ورود دستی"}
                    </button>
                  </div>
                  {symbol && (
                    <p className="text-xs text-gray-500 mt-1">
                      نماد انتخاب‌شده: {symbol}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">نوع هشدار</label>
                  <select value={alertType} onChange={(e) => setAlertType(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white">
                    {ALERT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">آستانه (Threshold)</label>
                  <input type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">توضیحات</label>
                  <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2 text-white" placeholder="اختیاری" />
                </div>
              </div>
              <button type="submit" className="bg-primary-600 hover:bg-primary-500 text-white rounded-lg px-6 py-2 text-sm font-medium transition">ایجاد هشدار</button>
            </form>
          </div>
        )}

         {loading ? (
           <div className="space-y-3">
             <Skeleton className="h-16 w-full rounded-xl" />
             <Skeleton className="h-16 w-full rounded-xl" />
             <Skeleton className="h-16 w-full rounded-xl" />
             <Skeleton className="h-16 w-full rounded-xl" />
           </div>
         ) : alerts.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <p className="text-gray-500 text-lg mb-2">هیچ هشداری تعریف نشده</p>
            <p className="text-gray-600 text-sm">روی دکمه &quot;هشدار جدید&quot; کلیک کنید تا اولین هشدار خود را ایجاد کنید</p>
            <p className="text-gray-600 text-xs mt-2">هشدارها بر اساس قیمت لحظه‌ای، حجم، RSI و عبور از میانگین بررسی می‌شوند</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div key={alert.id} className="glass-card p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <button onClick={() => toggleAlert(alert)} className={`w-10 h-6 rounded-full transition relative ${alert.enabled ? "bg-emerald-600" : "bg-surface-700"}`}>
                      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition ${alert.enabled ? "left-0.5" : "right-0.5"}`} />
                    </button>
                    <div>
                      <p className="font-medium">{alert.symbol} — {ALERT_TYPES.find(t => t.value === alert.alert_type)?.label || alert.alert_type}</p>
                      <p className="text-xs text-gray-500">آستانه: {String(alert.condition?.threshold ?? "-")} | فعال‌سازی: {alert.triggered_count} بار</p>
                      {alert.description && <p className="text-xs text-gray-600 mt-0.5">{alert.description}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${alert.enabled ? "bg-emerald-500/10 text-emerald-400" : "bg-surface-700 text-gray-500"}`}>
                      {alert.enabled ? "فعال" : "غیرفعال"}
                    </span>
                    <button onClick={() => fetchHistory(alert.id)} className="text-primary-400 hover:text-primary-300 text-xs px-2 py-1 rounded-lg bg-primary-600/10">
                      {historyAlertId === alert.id ? "بستن" : "تاریخچه"}
                    </button>
                    <button onClick={() => deleteAlert(alert.id)} className="text-rose-400 hover:text-rose-300 text-sm">حذف</button>
                  </div>
                </div>
                {/* Alert History */}
                {historyAlertId === alert.id && (
                  <div className="mt-3 pt-3 border-t border-surface-700/50">
                    {historyData.length === 0 ? (
                      <p className="text-xs text-gray-500 text-center py-2">تاریخچه‌ای موجود نیست</p>
                    ) : (
                      <div className="space-y-1">
                        {historyData.map((h) => (
                          <div key={h.id} className="flex items-center justify-between text-xs py-1 px-2 bg-surface-800/30 rounded">
                            <span className="text-gray-400">{new Date(h.triggered_at).toLocaleString("fa-IR")}</span>
                            <span className="font-mono text-surface-200">{h.trigger_value?.toLocaleString("en-US")}</span>
                            <span className="text-gray-500 truncate max-w-[200px]">{h.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
    </AppLayout>
  );
}