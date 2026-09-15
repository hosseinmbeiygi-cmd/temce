"use client";

import React, { useState, useRef, useEffect } from "react";
import { apiPost } from "@/lib/api";

interface Message {
  id: number;
  role: "user" | "assistant";
  text: string;
  ts: number;
}

const SUGGESTIONS = [
  "حباب سکه چقدره؟ الان بخرم؟",
  "P&L من چقدره؟",
  "الان چه کار کنم؟",
  "چرا حباب بالاست؟",
  "پله بعدی DCA فعال شد؟",
  "بهترین ابزار برای خرید چیه؟",
];

export default function GoldChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);
  const [hydrated, setHydrated] = useState(false);

  // init message on client only
  useEffect(() => {
    if (!hydrated) {
      idRef.current = 1;
      setMessages([
        {
          id: 1,
          role: "assistant",
          text: "سلام! من دستیار GoldDesk هستم. می‌توانم در مورد بازار، portfolio، و تصمیم‌گیری طلا کمکتان کنم. چه سؤالی دارید؟",
          ts: Date.now(),
        },
      ]);
      setHydrated(true);
    }
  }, [hydrated]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const send = React.useCallback(async (text: string) => {
    const msg = text.trim();
    if (!msg || loading) return;

    const userMsg: Message = { id: ++idRef.current, role: "user", text: msg, ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const r = await apiPost<{ success: boolean; data: { answer: string } }>("/api/gold/chat", { message: msg });
      const ans = r.data?.answer ?? "خطا در دریافت پاسخ.";
      setMessages((prev) => [...prev, { id: ++idRef.current, role: "assistant", text: ans, ts: Date.now() }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: ++idRef.current, role: "assistant", text: "⚠️ خطا در ارتباط با سرور.", ts: Date.now() },
      ]);
    } finally {
      setLoading(false);
    }
  }, [loading]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col" style={{ height: "calc(100vh - 12rem)" }} dir="rtl">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2 text-sm" style={{ color: "var(--gd-text-2)" }}>
        <span className="w-2 h-2 rounded-full bg-emerald-400" />
        <span>دستیار GoldDesk — با context کامل بازار و portfolio</span>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded-2xl p-4 space-y-3"
        style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}
      >
        {messages.map((m) => (
          <MessageBubble key={m.id} msg={m} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--gd-text-2)" }}>
            <TypingDots />
            <span>در حال فکر کردن...</span>
          </div>
        )}
      </div>

      {/* Suggestions */}
      {messages.length <= 2 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              disabled={loading}
              className="text-xs px-3 py-1.5 rounded-full transition disabled:opacity-50"
              style={{
                background: "var(--gd-bg-2)",
                color: "var(--gd-text-2)",
                border: "1px solid var(--gd-border)",
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="سؤال خود را بنویسید..."
          disabled={loading}
          className="flex-1 px-4 py-3 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/40 disabled:opacity-50"
          style={{ background: "var(--gd-bg-2)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-3 rounded-xl text-sm font-semibold transition disabled:opacity-50"
          style={{ background: "var(--gd-accent)", color: "#0f0a05" }}
        >
          ارسال
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
      <div
        className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
        style={{
          background: isUser ? "var(--gd-bg-3)" : "var(--gd-accent)",
          color: isUser ? "var(--gd-text)" : "#0f0a05",
        }}
      >
        <div className="whitespace-pre-wrap">{msg.text}</div>
        <div
          className={`text-[10px] mt-1 ${isUser ? "text-zinc-500" : "text-zinc-700"}`}
        >
          {new Date(msg.ts).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex gap-1">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: "300ms" }} />
    </div>
  );
}
