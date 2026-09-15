"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getHealth, getTelegramStatus, testTelegram, getWatchlist, putWatchlist } from "@/lib/goldApi";

export default function GoldSettingsPage() {
  const qc = useQueryClient();
  const [chatId, setChatId] = useState("");

  const { data: health } = useQuery({
    queryKey: ["gold", "health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const { data: tg } = useQuery({
    queryKey: ["gold", "telegram", "status"],
    queryFn: getTelegramStatus,
  });

  const { data: wl } = useQuery({
    queryKey: ["gold", "watchlist"],
    queryFn: getWatchlist,
  });

  const onTest = async () => {
    const r = await testTelegram(chatId || undefined);
    if (r.success) alert("✅ پیام تست ارسال شد");
    else alert("❌ " + (r.error?.message ?? "خطا"));
  };

  const [newSymbol, setNewSymbol] = useState("");
  const onAddSymbol = async () => {
    if (!newSymbol) return;
    const updated = [...(wl?.symbols ?? []), newSymbol];
    await putWatchlist(updated);
    qc.invalidateQueries({ queryKey: ["gold", "watchlist"] });
    setNewSymbol("");
  };

  const onRemoveSymbol = async (sym: string) => {
    const updated = (wl?.symbols ?? []).filter((s) => s !== sym);
    await putWatchlist(updated);
    qc.invalidateQueries({ queryKey: ["gold", "watchlist"] });
  };

  return (
    <div className="max-w-3xl space-y-6" dir="rtl">
      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-zinc-300">وضعیت سیستم</h3>
        {health ? (
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">Database</div>
              <div className={health.db_ok ? "text-emerald-400" : "text-rose-400"}>
                {health.db_ok ? "✓ OK" : "✗ FAIL"}
              </div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">Redis</div>
              <div className={health.redis_ok ? "text-emerald-400" : "text-rose-400"}>
                {health.redis_ok ? "✓ OK" : "✗ FAIL"}
              </div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">BrsApi</div>
              <div className={health.brsapi_ok ? "text-emerald-400" : "text-rose-400"}>
                {health.brsapi_ok ? "✓ OK" : "✗ FAIL"}
              </div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">Telegram</div>
              <div className={health.telegram_configured ? "text-emerald-400" : "text-amber-400"}>
                {health.telegram_configured ? "✓ پیکربندی شده" : "⚠ پیکربندی نشده"}
              </div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">قوانین فعال</div>
              <div className="text-zinc-100">{health.active_alert_rules}</div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">اعلان‌های خوانده‌نشده</div>
              <div className="text-zinc-100">{health.unread_alerts}</div>
            </div>
          </div>
        ) : (
          <div className="text-zinc-500">در حال بارگذاری...</div>
        )}
      </div>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-zinc-300">Telegram</h3>
        {tg && (
          <div className="text-xs text-zinc-400">
            Bot: {tg.data.bot_configured ? "✓" : "✗"} | Default chat_id:{" "}
            {tg.data.default_chat_id_set ? "✓" : "✗"} | Enabled: {tg.data.enabled ? "✓" : "✗"}
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="chat_id (برای تست)"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
          />
          <button onClick={onTest} className="bg-emerald-600 hover:bg-emerald-500 text-white rounded px-4 py-2 text-sm">
            ارسال تست
          </button>
        </div>
        <div className="text-[10px] text-zinc-500">
          برای تنظیم Bot Token و Chat ID پیش‌فرض، env variableهای GOLD_TELEGRAM_BOT_TOKEN، GOLD_TELEGRAM_CHAT_ID و
          GOLD_TELEGRAM_ENABLED=true را ست کنید.
        </div>
      </div>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-zinc-300">Watchlist</h3>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="نماد (مثل IR_GOLD_18K یا coin_emami)"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value)}
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
          />
          <button onClick={onAddSymbol} className="bg-emerald-600 hover:bg-emerald-500 text-white rounded px-4 py-2 text-sm">
            افزودن
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {(wl?.symbols ?? []).map((s) => (
            <div key={s} className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1 text-xs flex items-center gap-2">
              <span className="text-zinc-200">{s}</span>
              <button onClick={() => onRemoveSymbol(s)} className="text-rose-400 hover:text-rose-300">
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
