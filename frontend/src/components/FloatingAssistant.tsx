"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiPost } from "@/lib/api";
import { useRouter } from "next/navigation";

// ── Types ────────────────────────────────────────────────────────────────────

interface AssistantAction {
  type: string;
  label: string;
  url: string;
}

interface AssistantResponse {
  text: string;
  type: string;
  actions: AssistantAction[];
  link: string | null;
  link_label: string | null;
  data: Record<string, unknown> | null;
  suggestions: string[];
}

interface Message {
  role: "user" | "assistant";
  text: string;
  type?: string;
  actions?: AssistantAction[];
  link?: string | null;
  linkLabel?: string | null;
  suggestions?: string[];
  data?: Record<string, unknown> | null;
}

// ── Persian numerals helper ──────────────────────────────────────────────────

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
const ARABIC_DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

function formatText(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-white font-bold">{part.slice(2, -2)}</strong>;
    }
    return part.split("\n").map((line, j) => (
      <span key={`${i}-${j}`}>
        {j > 0 && <br />}
        {line}
      </span>
    ));
  });
}

// ── Floating Assistant Component ────────────────────────────────────────────

export default function FloatingAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "سلام! 👋 من دستیار هوشمند بازار سرمایه هستم.\n\nچطور می‌توانم کمک کنم؟",
      suggestions: [
        "بازار چطوره؟",
        "تحلیل فولاد",
        "بهترین سهم‌ها",
        "پرتفوی من",
        "اضافه فولاد به دیده‌بان",
        "help",
      ],
    },
  ]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // ── API Mutation ──
  const assistantMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await apiPost<{ success: boolean; data: AssistantResponse }>(
        "/assistant/execute",
        { message }
      );
      if (!res?.success) throw new Error("Assistant failed");
      return res.data;
    },
    onSuccess: (data) => {
      const msg: Message = {
        role: "assistant",
        text: data.text,
        actions: data.actions,
        link: data.link,
        linkLabel: data.link_label,
        suggestions: data.suggestions,
        data: data.data,
      };
      setMessages((prev) => [...prev, msg]);
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

  // ── Send message ──
  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || assistantMutation.isPending) return;

      setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
      setInput("");
      assistantMutation.mutate(trimmed);
    },
    [assistantMutation]
  );

  // ── Handle action click ──
  const handleAction = useCallback(
    (action: AssistantAction) => {
      if (action.type === "navigate" && action.url) {
        router.push(action.url);
        setIsOpen(false);
      } else if (action.type === "link" && action.url) {
        router.push(action.url);
        setIsOpen(false);
      }
    },
    [router]
  );

  // ── Auto-scroll ──
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Auto-focus input when opened ──
  useEffect(() => {
    if (isOpen && !isMinimized) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, isMinimized]);

  // ── Type color mapping ──
  const getTypeIcon = (type: string): string => {
    const icons: Record<string, string> = {
      greeting: "👋",
      market: "📊",
      analysis: "📈",
      comparison: "⚖️",
      screener: "🔍",
      watchlist: "👁️",
      alerts: "🔔",
      alert: "🔔",
      portfolio: "💼",
      backtest: "🧪",
      ml: "🧠",
      news: "📰",
      codal: "🏢",
      macro: "🏛️",
      heatmap: "🗺️",
      risk: "🛡️",
      report: "📋",
      anomalies: "🚨",
      signals: "📡",
      navigation: "🔗",
      help: "❓",
      farewell: "🙏",
      refresh: "🔄",
      error: "⚠️",
      unknown: "🤔",
    };
    return icons[type] || "🤖";
  };

  const getTypeColor = (type: string): string => {
    if (type === "error") return "border-r-accent-rose";
    if (type === "market" || type === "analysis") return "border-r-primary-400";
    if (type === "action") return "border-r-accent-emerald";
    if (type === "navigation") return "border-r-accent-violet";
    if (type === "watchlist" || type === "alerts") return "border-r-accent-amber";
    if (type === "backtest" || type === "ml") return "border-r-accent-cyan";
    return "border-r-surface-500";
  };

  // ── Auto-minimize after longer inactivity (only on initial welcome)
  useEffect(() => {
    if (!isOpen || isMinimized || messages.length > 1) return;
    const timer = setTimeout(() => {
      if (messages.length <= 1) setIsMinimized(true);
    }, 120000); // 2 minutes
    return () => clearTimeout(timer);
  }, [isOpen, isMinimized, messages.length]);

  // ── Render ──
  return (
    <>
      {/* ── Toggle Button ── */}
      <button
        onClick={() => {
          setIsOpen(!isOpen);
          setIsMinimized(false);
        }}
        className={`fixed bottom-5 right-5 z-50 w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 ${
          isOpen
            ? "bg-surface-800 rotate-45 scale-90"
            : "bg-primary-600 hover:bg-primary-500 hover:scale-110"
        }`}
        title="دستیار هوشمند"
      >
        <span className="material-icons text-2xl text-white">
          {isOpen ? "close" : "smart_toy"}
        </span>
      </button>

      {/* ── Chat Window ── */}
      {isOpen && (
        <div
          dir="rtl"
          className={`fixed bottom-20 right-5 z-50 w-80 sm:w-96 glass-card border border-surface-700/50 shadow-2xl rounded-2xl overflow-hidden transition-all duration-300 flex flex-col ${
            isMinimized ? "h-14" : "h-[600px] max-h-[80vh]"
          }`}
        >
          {/* ── Header ── */}
          <div className="shrink-0 px-4 py-3 border-b border-surface-700/50 flex items-center justify-between bg-surface-900/50">
            <div className="flex items-center gap-2">
              <span className="material-icons text-primary-400 text-lg">smart_toy</span>
              <div>
                <p className="text-sm font-bold text-surface-200">دستیار هوشمند</p>
                <p className="text-[9px] text-surface-500">آزمایشی · تمام قابلیت‌ها</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsMinimized(!isMinimized)}
                className="p-1 rounded-lg hover:bg-surface-700 text-surface-400 hover:text-surface-200 transition-all"
                title={isMinimized ? "باز کردن" : "کوچک کردن"}
              >
                <span className="material-icons text-sm">
                  {isMinimized ? "expand_less" : "remove"}
                </span>
              </button>
            </div>
          </div>

          {!isMinimized && (
            <>
              {/* ── Messages ── */}
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-start" : "justify-start"}`}>
                    <div
                      className={`max-w-[92%] rounded-2xl p-3 ${
                        msg.role === "user"
                          ? "bg-primary-600/20 border border-primary-600/20 text-surface-200 rounded-br-md"
                          : `bg-surface-800/50 border border-surface-700/30 rounded-bl-md border-r-2 ${getTypeColor(msg.type || "text")}`
                      }`}
                    >
                      {/* Avatar */}
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span>{msg.role === "user" ? "👤" : getTypeIcon(msg.type || "text")}</span>
                        <span className="text-[9px] text-surface-500 font-bold">
                          {msg.role === "user" ? "شما" : "دستیار"}
                        </span>
                      </div>

                      {/* Text */}
                      <div className="text-xs text-surface-300 leading-relaxed whitespace-pre-wrap">
                        {formatText(msg.text)}
                      </div>

                      {/* Actions */}
                      {msg.actions && msg.actions.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {msg.actions.map((action, j) => (
                            <button
                              key={j}
                              onClick={() => handleAction(action)}
                              className={`text-[9px] px-2.5 py-1 rounded-lg transition-all font-medium ${
                                action.type === "navigate"
                                  ? "bg-accent-violet/20 hover:bg-accent-violet/30 text-accent-violet border border-accent-violet/30"
                                  : "bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 border border-primary-600/30"
                              }`}
                            >
                              {action.label || action.url}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Link */}
                      {msg.link && (
                        <button
                          onClick={() => router.push(msg.link!)}
                          className="inline-flex items-center gap-1 mt-2 px-2.5 py-1 bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 rounded-lg text-[10px] font-medium transition-colors"
                        >
                          <span className="material-icons text-xs">open_in_new</span>
                          {msg.linkLabel || "مشاهده"}
                        </button>
                      )}

                      {/* Suggestions */}
                      {msg.suggestions && msg.suggestions.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {msg.suggestions.slice(0, 4).map((s, j) => (
                            <button
                              key={j}
                              onClick={() => sendMessage(s)}
                              disabled={assistantMutation.isPending}
                              className="text-[9px] px-2 py-1 bg-surface-800 hover:bg-surface-700 text-surface-400 hover:text-surface-200 rounded-lg transition-all disabled:opacity-50"
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {/* Typing indicator */}
                {assistantMutation.isPending && (
                  <div className="flex justify-start">
                    <div className="bg-surface-800/50 border border-surface-700/30 rounded-2xl rounded-bl-md p-3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs">🤖</span>
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    </div>
                  </div>
                )}

                <div ref={endRef} />
              </div>

              {/* ── Input ── */}
              <div className="shrink-0 p-3 border-t border-surface-700/50">
                <div className="flex items-center gap-2">
                  <input
                    ref={inputRef}
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
                    className="flex-1 bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 text-xs text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
                    disabled={assistantMutation.isPending}
                  />
                  <button
                    onClick={() => sendMessage(input)}
                    disabled={!input.trim() || assistantMutation.isPending}
                    className="p-2 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl transition-all"
                  >
                    <span className="material-icons text-sm">send</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
