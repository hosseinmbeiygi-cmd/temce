"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface ChatResponse {
  text: string;
  suggestions: string[];
  link: string | null;
  link_label: string | null;
  data: Record<string, unknown> | null;
}

interface Message {
  role: "user" | "assistant";
  text: string;
  suggestions?: string[];
  link?: string | null;
  linkLabel?: string | null;
}

// ── Initial assistant message ───────────────────────────────────────────────────────────────────────────────────────────────────────

const WELCOME_MSG: Message = {
  role: "assistant",
  text: "سلام! 🤖 من دستیار هوشمند بازار سرمایه هستم. می‌توانم در این موارد به شما کمک کنم:\n\n"
    + "📊 **اطلاعات نمادها** — قیمت، تغییرات، تحلیل نمادهای بورسی\n"
    + "📈 **تحلیل بازار** — روندها، شاخص‌ها، احساسات بازار\n"
    + "🔍 **غربال‌گری** — یافتن بهترین نمادها با ۵ فاز Smart Money\n"
    + "🧠 **یادگیری ماشین** — پیش‌بینی قیمت با مدل‌های AI\n"
    + "🏦 **صندوق‌ها** — اطلاعات NAV و عملکرد صندوق‌ها\n"
    + "📰 **اخبار** — آخرین اخبار و تحلیل احساسات\n"
    + "📊 **نمودارها** — اندیکاتورهای تکنیکال و تاریخچه قیمت\n\n"
    + "یک سوال بپرسید یا روی یکی از پیشنهادات زیر کلیک کنید! 👇",
  suggestions: [
    "قیمت فولاد چقدره؟",
    "بهترین نمادها کدامند؟",
    "تحلیل بازار امروز چطوره؟",
    "صندوق‌ها رو نشون بده",
    "پیش‌بینی قیمت سهم",
    "ناهنجاری‌های بازار",
  ],
};

// ── Format message text (bold, newlines) ─────────────────────────────────────────────────────────────────────────────────────────────

function formatText(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-surface-100">{part.slice(2, -2)}</strong>;
    }
    return part.split("\n").map((line, j) => (
      <span key={`${i}-${j}`}>
        {j > 0 && <br />}
        {line}
      </span>
    ));
  });
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MSG]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await apiPost<{ success: boolean; data: ChatResponse }>("/chat", { message });
      if (!res?.success) throw new Error("Chat failed");
      return res.data;
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.text,
          suggestions: data.suggestions,
          link: data.link,
          linkLabel: data.link_label,
        },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
        },
      ]);
    },
  });

  const sendMessage = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || chatMutation.isPending) return;
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setInput("");
    chatMutation.mutate(trimmed);
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <AppLayout title="🤖 دستیار هوشمند" subtitle="پرسش و پاسخ بازار سرمایه">
      <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-12rem)]">
        {/* ── Messages ── */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 px-1">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-start" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl p-4 ${
                  msg.role === "user"
                    ? "bg-primary-600/20 border border-primary-600/20 text-surface-200 rounded-br-md"
                    : "glass-card rounded-bl-md"
                }`}
              >
                {/* Avatar */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">
                    {msg.role === "user" ? "👤" : "🤖"}
                  </span>
                  <span className="text-[10px] text-surface-500 font-bold">
                    {msg.role === "user" ? "شما" : "دستیار هوشمند"}
                  </span>
                </div>

                {/* Text */}
                <div className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                  {formatText(msg.text)}
                </div>

                {/* Link */}
                {msg.link && (
                  <Link
                    href={msg.link}
                    className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 rounded-lg text-xs font-medium transition-colors"
                  >
                    <span>🔗</span>
                    {msg.linkLabel || "مشاهده"}
                  </Link>
                )}

                {/* Suggestions */}
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {msg.suggestions.map((s, j) => (
                      <button
                        key={j}
                        onClick={() => sendMessage(s)}
                        disabled={chatMutation.isPending}
                        className="text-[10px] px-2.5 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-surface-200 rounded-lg transition-all disabled:opacity-50"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* ── Typing indicator ── */}
          {chatMutation.isPending && (
            <div className="flex justify-start">
              <div className="glass-card rounded-2xl rounded-bl-md p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">🤖</span>
                  <span className="text-[10px] text-surface-500">در حال فکر کردن...</span>
                </div>
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-surface-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-surface-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-surface-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        {/* ── Input ── */}
        <div className="glass-card p-3 flex items-center gap-2 sticky bottom-0">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
            placeholder="سوال خود را بپرسید..."
            className="flex-1 bg-surface-800 border border-surface-700 rounded-xl px-4 py-3 text-sm text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
            disabled={chatMutation.isPending}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || chatMutation.isPending}
            className="p-3 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl transition-all"
          >
            <span className="material-icons text-sm">send</span>
          </button>
        </div>
      </div>
    </AppLayout>
  );
}
