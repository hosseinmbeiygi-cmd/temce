"use client";
import React, { useState } from "react";
import { createAlertRule } from "@/lib/goldApi";

interface Props {
  onCreated?: () => void;
  className?: string;
}

const RULE_TYPES = [
  { value: "bubble_above", label: "حباب بالاتر از" },
  { value: "bubble_below", label: "حباب پایین‌تر از" },
  { value: "nav_bubble_above", label: "NAV حباب بالاتر از" },
  { value: "score_above", label: "امتیاز بالاتر از" },
  { value: "score_below", label: "امتیاز پایین‌تر از" },
  { value: "price_above", label: "قیمت بالاتر از" },
  { value: "parity_gap_above", label: "شکاف درهم بیشتر از" },
];

export function AlertRuleForm({ onCreated, className = "" }: Props) {
  const [name, setName] = useState("");
  const [ruleType, setRuleType] = useState("bubble_above");
  const [symbol, setSymbol] = useState("");
  const [threshold, setThreshold] = useState(20);
  const [channel, setChannel] = useState<"inapp" | "telegram" | "both">("inapp");
  const [chatId, setChatId] = useState("");
  const [cooldown, setCooldown] = useState(30);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createAlertRule({
        name,
        rule_type: ruleType,
        symbol: symbol || undefined,
        threshold,
        channel,
        telegram_chat_id: chatId || undefined,
        cooldown_minutes: cooldown,
      });
      setName("");
      setSymbol("");
      onCreated?.();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className={`space-y-3 p-4 border border-zinc-700 rounded-lg bg-zinc-900 ${className}`}>
      <div className="text-sm font-semibold text-zinc-300 mb-2">قانون جدید</div>
      <input
        type="text"
        placeholder="نام قانون"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
        required
      />
      <select
        value={ruleType}
        onChange={(e) => setRuleType(e.target.value)}
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
      >
        {RULE_TYPES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <input
        type="text"
        placeholder="نماد (اختیاری، مثل coin_emami)"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
      />
      <div className="flex gap-2">
        <input
          type="number"
          step="0.1"
          value={threshold}
          onChange={(e) => setThreshold(parseFloat(e.target.value))}
          className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
        />
        <input
          type="number"
          value={cooldown}
          onChange={(e) => setCooldown(parseInt(e.target.value))}
          className="w-24 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
          placeholder="دقیقه"
        />
      </div>
      <select
        value={channel}
        onChange={(e) => setChannel(e.target.value as "inapp" | "telegram" | "both")}
        className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
      >
        <option value="inapp">In-app</option>
        <option value="telegram">Telegram</option>
        <option value="both">هر دو</option>
      </select>
      {channel !== "inapp" && (
        <input
          type="text"
          placeholder="Telegram chat_id"
          value={chatId}
          onChange={(e) => setChatId(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
        />
      )}
      <button
        type="submit"
        disabled={submitting || !name}
        className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold"
      >
        {submitting ? "در حال ثبت..." : "ثبت قانون"}
      </button>
    </form>
  );
}
