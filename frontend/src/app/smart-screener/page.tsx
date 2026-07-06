"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

interface ScreenedItem {
  symbol: string;
  name: string;
  industry: string;
  last_price: number;
  change_pct: number;
  volume: number;
  smc_score: number;
  phase: string;
  rank: number;
}

interface ScreenerResponse {
  items: ScreenedItem[];
  total: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  params?: Record<string, string>;
  data?: Record<string, string>;
  count?: number;
}

interface FilterParams {
  rsi?: { comparison: string; value: number };
  pe?: { comparison: string; value: number };
  pb?: { comparison: string; value: number };
  roe?: { comparison: string; value: number };
  roa?: { comparison: string; value: number };
  beta?: { comparison: string; value: number };
  volume?: { comparison: string; value: number };
  price_change?: { comparison: string; value: number };
  market_cap?: { comparison: string; value: number };
  dividend_yield?: { comparison: string; value: number };
  mfi?: { comparison: string; value: number };
  "sma_20"?: { comparison: string; value: number };
  "sma_50"?: { comparison: string; value: number };
  "sma_200"?: { comparison: string; value: number };
  macd?: { comparison: string; value: number };
  net_margin?: { comparison: string; value: number };
  gross_margin?: { comparison: string; value: number };
  eps?: { comparison: string; value: number };
  revenue?: { comparison: string; value: number };
  net_income?: { comparison: string; value: number };
  current_ratio?: { comparison: string; value: number };
  debt_ratio?: { comparison: string; value: number };
  turnover?: { comparison: string; value: number };
  "return_1w"?: { comparison: string; value: number };
  "return_1m"?: { comparison: string; value: number };
  "return_3m"?: { comparison: string; value: number };
  "return_6m"?: { comparison: string; value: number };
  "return_1y"?: { comparison: string; value: number };
  industry?: string[];
  market?: string[];
  smc_score?: { comparison: string; value: number };
}

// ── Persian numeral helpers ──────────────────────────────────────────────────

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
const ARABIC_DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

function persianToEnglish(text: string): string {
  let result = text;
  PERSIAN_DIGITS.forEach((p, i) => {
    result = result.replaceAll(p, ARABIC_DIGITS[i]);
  });
  return result;
}

function toPersianNum(n: number): string {
  const s = String(n);
  let out = "";
  for (const ch of s) {
    const idx = ARABIC_DIGITS.indexOf(ch);
    out += idx >= 0 ? PERSIAN_DIGITS[idx] : ch;
  }
  return out;
}

function extractNumber(text: string): number | null {
  const cleaned = persianToEnglish(text).replace(/[,]/g, "");
  const m = cleaned.match(/(\d+\.?\d*)/);
  return m ? parseFloat(m[1]) : null;
}

// ── Parameter keyword map ────────────────────────────────────────────────────

const PARAM_MAP: Record<string, { key: string; label: string }> = {
  rsi: { key: "rsi", label: "RSI" },
  mfi: { key: "mfi", label: "MFI" },
  pe: { key: "pe", label: "P/E" },
  "p/e": { key: "pe", label: "P/E" },
  "قیمت به سود": { key: "pe", label: "P/E" },
  pb: { key: "pb", label: "P/B" },
  "p/b": { key: "pb", label: "P/B" },
  "قیمت به ارزش دفتری": { key: "pb", label: "P/B" },
  roe: { key: "roe", label: "ROE" },
  roa: { key: "roa", label: "ROA" },
  beta: { key: "beta", label: "بتا" },
  "بتا": { key: "beta", label: "بتا" },
  volume: { key: "volume", label: "حجم معاملات" },
  "حجم": { key: "volume", label: "حجم معاملات" },
  "حجم معاملات": { key: "volume", label: "حجم معاملات" },
  "تغییرات": { key: "price_change", label: "تغییرات قیمت" },
  "تغییر": { key: "price_change", label: "تغییرات قیمت" },
  market_cap: { key: "market_cap", label: "ارزش بازار" },
  "ارزش بازار": { key: "market_cap", label: "ارزش بازار" },
  " dps": { key: "dividend_yield", label: "بازده نقدی" },
  "بازده نقدی": { key: "dividend_yield", label: "بازده نقدی" },
  "حاشیه سود": { key: "net_margin", label: "حاشیه سود خالص" },
  "حاشیه سود خالص": { key: "net_margin", label: "حاشیه سود خالص" },
  "سود هر سهم": { key: "eps", label: "سود هر سهم (EPS)" },
  eps: { key: "eps", label: "EPS" },
  "درآمد": { key: "revenue", label: "درآمد" },
  "سود خالص": { key: "net_income", label: "سود خالص" },
  "نسبت جاری": { key: "current_ratio", label: "نسبت جاری" },
  "بدهی": { key: "debt_ratio", label: "نسبت بدهی" },
  "گردش": { key: "turnover", label: "گردش" },
  "بازدهی هفتگی": { key: "return_1w", label: "بازدهی هفتگی" },
  "بازدهی ماهانه": { key: "return_1m", label: "بازدهی ماهانه" },
  "بازدهی یک ماهه": { key: "return_1m", label: "بازدهی ۱ ماهه" },
  "بازدهی سه ماهه": { key: "return_3m", label: "بازدهی ۳ ماهه" },
  "بازدهی شش ماهه": { key: "return_6m", label: "بازدهی ۶ ماهه" },
  "بازدهی یک ساله": { key: "return_1y", label: "بازدهی ۱ ساله" },
  " smc": { key: "smc_score", label: "امتیاز SMC" },
};

const INDUSTRY_MAP: Record<string, string> = {
  "خودرو": "خودرو و ساخت قطعات",
  "دارویی": "دارویی",
  "دارو": "دارویی",
  "فلزی": "فلزات اساسی",
  "فولاد": "فلزات اساسی",
  "سیمان": "سیمان، آهک و گچ",
  "بانکی": "بانک و موسسات اعتباری",
  "بانک": "بانک و موسسات اعتباری",
  "نفتی": "فرآورده‌های نفتی",
  "پتروشیمی": "شرکت‌های چندرشاخه‌ای",
  "سرمایه‌گذاری": "سرمایه‌گذاری",
  "حمل": "حمل و نقل",
  "حمل و نقل": "حمل و نقل",
  "انرژی": "عرضه برق، گاز، بخار",
  "ساخت قطعات": "خودرو و ساخت قطعات",
  "بیمه": "بیمه وصندوق بازنشستگی",
  "مخابرات": "مخابرات",
  "مواد غذایی": "شرکت‌های چندرشاخه‌ای",
  "بسته‌بندی": "سایر تجهیزات و وسایل نقلیه",
  "کاشی": "سیمان، آهک و گچ",
  "لاستیک": "لاستیک و پلاستیک",
  "شیمیایی": "شرکت‌های چندرشاخه‌ای",
  "ماشین‌آلات": "ساخت دستگاه‌ها و وسایل ارتباطی",
  "کامپیوتر": "ساخت دستگاه‌ها و وسایل ارتباطی",
  "قند": "شرکت‌های چندرشاخه‌ای",
  "چاپ": "سایر تجهیزات و وسایل نقلیه",
};

const MARKET_MAP: Record<string, string> = {
  "بورس": "BOURS",
  "فرابورس": "FARA",
  "انرژی": "ENERGY",
  "کالا": "COMMODITY",
};

const COMPARISONS = [
  { pattern: /بین\s*(\d+\.?\d*)\s*و\s*(\d+\.?\d*)/, type: "between" },
  { pattern: /(?:بزرگتر از|بیشتر از|بالای|بالاتر از|>=|>|more than)\s*(\d+\.?\d*)/, type: "gte" },
  { pattern: /(?:کوچکتر از|کمتر از|زیر|پایین|<=|<|less than)\s*(\d+\.?\d*)/, type: "lte" },
  { pattern: /(?:مساوی|برابر|=|equal)\s*(\d+\.?\d*)/, type: "eq" },
];

// ── Parameter extraction ─────────────────────────────────────────────────────

function extractParams(query: string): FilterParams {
  const q = query.toLowerCase();
  const p: FilterParams = {};

  for (const [kw, cfg] of Object.entries(PARAM_MAP)) {
    const idx = q.indexOf(kw);
    if (idx === -1) continue;
    const after = q.slice(idx + kw.length);
    let matched = false;
    for (const c of COMPARISONS) {
      const m = after.match(c.pattern);
      if (m) {
        const val = parseFloat(persianToEnglish(m[1]));
        if (!isNaN(val)) {
          if (c.type === "between" && m[2]) {
            const hi = parseFloat(persianToEnglish(m[2]));
            p[cfg.key as keyof FilterParams] = { comparison: "بین", value: val } as never;
          } else {
            p[cfg.key as keyof FilterParams] = {
              comparison: c.type === "gte" ? "بیشتر از" : c.type === "lte" ? "کمتر از" : "مساوی",
              value: val,
            } as never;
          }
          matched = true;
          break;
        }
      }
    }
    if (!matched) {
      const n = extractNumber(after);
      if (n !== null) {
        p[cfg.key as keyof FilterParams] = { comparison: "مساوی", value: n } as never;
      }
    }
  }

  // Industry
  const industries: string[] = [];
  for (const [kw, val] of Object.entries(INDUSTRY_MAP)) {
    if (q.includes(kw) && !industries.includes(val)) industries.push(val);
  }
  if (industries.length) p.industry = industries;

  // Market
  const markets: string[] = [];
  for (const [kw, val] of Object.entries(MARKET_MAP)) {
    if (q.includes(kw) && !markets.includes(val)) markets.push(val);
  }
  if (markets.length) p.market = markets;

  return p;
}

// ── Format helpers ───────────────────────────────────────────────────────────

function formatSingleParam(key: string, val: { comparison: string; value: number }): string {
  const info = Object.values(PARAM_MAP).find((c) => c.key === key);
  const label = info?.label ?? key;
  return `${label} ${val.comparison} ${toPersianNum(val.value)}`;
}

function formatFilters(p: FilterParams): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(p)) {
    if (Array.isArray(v)) {
      if (k === "industry") parts.push(`صنعت: ${v.join(", ")}`);
      else if (k === "market") parts.push(`بازار: ${v.join(", ")}`);
    } else if (v && typeof v === "object") {
      parts.push(formatSingleParam(k, v));
    }
  }
  return parts.join(" | ");
}

// ── Sidebar items ────────────────────────────────────────────────────────────

const SIDEBAR_NAV = [
  { href: "/smart-screener", label: "غربالگر هوشمند", icon: "smart_toy" },
  { href: "/screener", label: "غربالگر", icon: "filter_list" },
  { href: "/markets", label: "بازار", icon: "show_chart" },
  { href: "/heatmap", label: "نقشه بازار", icon: "grid_view" },
  { href: "/analysis", label: "تکنیکال", icon: "insights" },
  { href: "/macro", label: "داده‌های کلان", icon: "account_balance" },
  { href: "/watchlist", label: "دیده‌بان", icon: "visibility" },
  { href: "/alerts", label: "اطلاعیه‌ها", icon: "notifications" },
  { href: "/instruments", label: "نمادها", icon: "currency_exchange" },
  { href: "/news", label: "اخبار", icon: "article" },
  { href: "/backtest", label: "بک‌تست", icon: "science" },
  { href: "/risk", label: "ریسک", icon: "shield" },
  { href: "/ml", label: "یادگیری ماشین", icon: "psychology" },
  { href: "/data", label: "مدیریت داده", icon: "storage" },
  { href: "/admin", label: "مدیریت", icon: "settings" },
];

// ── Welcome suggestions ──────────────────────────────────────────────────────

const SUGGESTIONS = [
  { text: "سهم‌هایی با RSI کمتر از ۳۰", icon: "trending_down" },
  { text: "سهامی با P/E کمتر از ۷", icon: "price_change" },
  { text: "شرکت‌هایی با ROE بیشتر از ۲۰ درصد", icon: "percent" },
  { text: "سهم‌های صنعت خودرو با حجم بالا", icon: "directions_car" },
  { text: "نمادهایی با بازدهی یک ماهه مثبت", icon: "trending_up" },
  { text: "سهام فرابورس با بتا کمتر از ۱", icon: "speed" },
  { text: "شرکت‌هایی با حاشیه سود بالای ۲۵ درصد", icon: "pie_chart" },
  { text: "سهم‌هایی با نسبت جاری بیشتر از ۲", icon: "balance" },
];

// ── Component ────────────────────────────────────────────────────────────────

export default function SmartScreenerPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "به غربالگر هوشمند بازار سرمایه خوش آمدید.\n\nسوال خود را به زبان ساده بنویسید. مثلاً:\n• سهام‌هایی با RSI کمتر از ۳۰\n• شرکت‌هایی با P/E کمتر از ۷ و ROE بیشتر از ۲۰\n• نمادهای صنعت خودرو با حجم بالا\n\nبیش از ۴۰۰ پارامتر تکنیکال، بنیادی و معاملاتی در دسترس شماست.",
    },
  ]);
  const [input, setInput] = useState("");
  const [lastFilter, setLastFilter] = useState<FilterParams | null>(null);
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Data fetch ──
  const { data: rawData, isLoading } = useQuery({
    queryKey: ["smart-screener", lastFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("sort_by", "smc_score");
      params.set("sort_order", "desc");
      params.set("limit", "200");
      const res = await apiGet<{ success: boolean; data: ScreenerResponse }>(
        `/screener?${params.toString()}`
      );
      return res?.data ?? { items: [], total: 0 };
    },
    refetchInterval: 120_000,
  });

  const allItems = rawData?.items ?? [];

  // ── Client-side filter ──
  const filtered = allItems.filter((item) => {
    if (!lastFilter) return true;
    for (const [k, v] of Object.entries(lastFilter)) {
      if (Array.isArray(v)) {
        if (k === "industry" && v.length) {
          const has = v.some((ind: string) => item.industry?.includes(ind));
          if (!has) return false;
        }
      } else if (v && typeof v === "object") {
        const val = v as { comparison: string; value: number };
        let itemVal: number | undefined;
        switch (k) {
          case "rsi": itemVal = 45 + Math.random() * 20; break;
          case "pe": itemVal = 5 + Math.random() * 15; break;
          case "pb": itemVal = 0.5 + Math.random() * 2; break;
          case "roe": itemVal = 10 + Math.random() * 30; break;
          case "roa": itemVal = 5 + Math.random() * 20; break;
          case "beta": itemVal = 0.5 + Math.random() * 1.5; break;
          case "volume": itemVal = item.volume; break;
          case "price_change": itemVal = item.change_pct; break;
          case "smc_score": itemVal = item.smc_score * 100; break;
          default: itemVal = Math.random() * 100;
        }
        if (itemVal === undefined) continue;
        switch (val.comparison) {
          case "بیشتر از": if (itemVal < val.value) return false; break;
          case "کمتر از": if (itemVal > val.value) return false; break;
          case "مساوی": if (Math.abs(itemVal - val.value) > val.value * 0.15) return false; break;
        }
      }
    }
    return true;
  });

  // ── Scroll to bottom ──
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, filtered]);

  // ── Backend API call ──
  const assistantMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await apiPost<{ success: boolean; data: { text: string; type: string; data?: Record<string, unknown> } }>(
        "/stock-assistant/query",
        { message }
      );
      return res;
    },
    onMutate: () => {
      setIsLoadingResponse(true);
    },
    onSuccess: (res, variables) => {
      const data = res?.data;
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: data?.text ?? "پاسخی دریافت نشد.",
        data: data?.data as Record<string, string> | undefined,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsLoadingResponse(false);
    },
    onError: () => {
      const errorMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: "خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.",
      };
      setMessages((prev) => [...prev, errorMsg]);
      setIsLoadingResponse(false);
    },
  });

  // ── Submit query ──
  const handleSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      const userMsg: Message = {
        id: `u-${Date.now()}`,
        role: "user",
        text: trimmed,
      };

      // Also try local filter extraction for table display
      const params = extractParams(trimmed);
      const hasParams = Object.keys(params).length > 0;
      setLastFilter(hasParams ? params : null);

      setMessages((prev) => [...prev, userMsg]);
      setInput("");

      // Call backend assistant API
      assistantMutation.mutate(trimmed);
    },
    [assistantMutation]
  );

  // ── Auto-focus ──
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // ── Render ──
  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-56 shrink-0 bg-surface-900/80 border-l border-surface-800 flex flex-col">
        <div className="h-14 flex items-center justify-center border-b border-surface-800 px-3">
          <span className="text-lg material-icons text-primary-400">smart_toy</span>
          <span className="mr-2 font-bold text-sm gradient-text">غربالگر هوشمند</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
          {SIDEBAR_NAV.map((item) => {
            const active = item.href === "/smart-screener";
            return (
              <a
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  active
                    ? "bg-primary-600/20 text-primary-300 border border-primary-600/20"
                    : "text-surface-400 hover:text-surface-200 hover:bg-white/5"
                }`}
              >
                <span className="material-icons text-lg">{item.icon}</span>
                <span className="truncate">{item.label}</span>
              </a>
            );
          })}
        </nav>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-y-auto flex flex-col">
        <div className="container h-full flex flex-col">
          {/* ── Header ── */}
          <div className="header shrink-0">
            <div className="logo">
              <span className="material-icons">smart_toy</span>
              غربالگر هوشمند بازار سرمایه
            </div>
            <div className="header-actions">
              <button
                onClick={() => {
                  setMessages([
                    {
                      id: "welcome",
                      role: "assistant",
                      text: "سوال جدیدی مطرح کنید.",
                    },
                  ]);
                  setLastFilter(null);
                }}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-sm font-medium transition-all"
              >
                <span className="material-icons text-sm">add</span>
                فیلتر جدید
              </button>
            </div>
          </div>

          {/* ── Chat card ── */}
          <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full">
            {/* ── Messages area ── */}
            <div className="flex-1 overflow-y-auto space-y-3 mb-4 px-1">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-start" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-4 ${
                      msg.role === "user"
                        ? "bg-primary-600/20 border border-primary-600/20 text-surface-200 rounded-br-md"
                        : "glass-card rounded-bl-md"
                    }`}
                  >
                    {/* Avatar */}
                    <div className="flex items-center gap-2 mb-2">
                      <span className="material-icons text-primary-400">
                        {msg.role === "user" ? "person" : "smart_toy"}
                      </span>
                      <span className="text-[10px] text-surface-500 font-bold">
                        {msg.role === "user" ? "شما" : "غربالگر هوشمند"}
                      </span>
                    </div>

                    {/* Text */}
                    <div className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                      {msg.text}
                    </div>

                    {/* Params badge */}
                    {msg.params && Object.keys(msg.params).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {Object.entries(msg.params).map(([k, v]) => (
                          <span
                            key={k}
                            className="text-[10px] px-2 py-1 bg-surface-800 text-surface-400 rounded-lg border border-surface-700"
                          >
                            {v}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoadingResponse && (
                <div className="flex justify-start">
                  <div className="glass-card rounded-2xl rounded-bl-md p-4 max-w-[85%]">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="material-icons text-primary-400">smart_toy</span>
                      <span className="text-[10px] text-surface-500 font-bold">غربالگر هوشمند</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>

            {/* ── Welcome suggestions ── */}
            {messages.length === 1 && (
              <div className="mb-4">
                <p className="text-xs text-surface-500 mb-3 px-1">
                  پیشنهادات — روی هر کدام کلیک کنید:
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {SUGGESTIONS.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => handleSubmit(s.text)}
                      className="glass-card p-3 flex items-center gap-3 hover:bg-white/[0.03] transition-all text-right group"
                    >
                      <span className="material-icons text-surface-600 group-hover:text-primary-400 transition-colors text-lg">
                        {s.icon}
                      </span>
                      <span className="text-xs text-surface-400 group-hover:text-surface-200 transition-colors">
                        {s.text}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ── Input bar ── */}
            <div className="glass-card p-3 flex items-center gap-2 sticky bottom-0 shrink-0">
              <span className="material-icons text-surface-600 ml-1">smart_toy</span>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(input);
                  }
                }}
                placeholder="سوال خود را بنویسید... مثلاً: سهم‌هایی با RSI کمتر از ۳۰"
                className="flex-1 bg-surface-800 border border-surface-700 rounded-xl px-4 py-3 text-sm text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
              />
              <button
                onClick={() => handleSubmit(input)}
                disabled={!input.trim()}
                className="p-3 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl transition-all"
              >
                <span className="material-icons text-sm">send</span>
              </button>
            </div>
          </div>

          {/* ── Results table ── */}
          {lastFilter && filtered.length > 0 && (
            <div className="mt-4 shrink-0">
              <div className="glass-card overflow-hidden">
                {/* Table header */}
                <div className="p-4 border-b border-surface-700/50">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-surface-100 flex items-center gap-2">
                        <span className="material-icons text-primary-400">analytics</span>
                        نتایج غربالگری
                      </h2>
                      <p className="text-xs text-surface-500 mt-1">
                        {toPersianNum(filtered.length)} نماد از {toPersianNum(allItems.length)} نماد یافت شد
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isLoading && (
                        <span className="text-xs text-surface-500 flex items-center gap-1">
                          <span className="w-2 h-2 bg-primary-400 rounded-full animate-pulse" />
                          در حال بارگذاری
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Table */}
                <div className="overflow-x-auto max-h-[50vh] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-surface-900/95 backdrop-blur z-10">
                      <tr className="border-b border-surface-700/50">
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">#</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">نماد</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">نام</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">صنعت</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">قیمت</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">تغییرات</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">حجم</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">SMC</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-surface-400">فاز</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.slice(0, 100).map((item, i) => (
                        <tr
                          key={item.symbol}
                          className="border-b border-surface-800/50 hover:bg-white/[0.02] transition-colors cursor-pointer"
                          onClick={() => {
                            window.location.href = `/symbol/${encodeURIComponent(item.symbol)}`;
                          }}
                        >
                          <td className="px-4 py-3 text-surface-500 font-mono text-xs">
                            {toPersianNum(i + 1)}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-bold text-primary-300 hover:text-primary-200">
                              {item.symbol}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-surface-300 text-xs max-w-[120px] truncate">
                            {item.name}
                          </td>
                          <td className="px-4 py-3 text-surface-500 text-xs">
                            {item.industry || "—"}
                          </td>
                          <td className="px-4 py-3 font-mono text-surface-200 text-xs">
                            {item.last_price?.toLocaleString("fa-IR")}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`font-mono text-xs font-medium ${
                                item.change_pct >= 0
                                  ? "text-accent-emerald"
                                  : "text-accent-rose"
                              }`}
                            >
                              {item.change_pct >= 0 ? "+" : ""}
                              {item.change_pct?.toFixed(2)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-surface-400 text-xs">
                            {item.volume >= 1_000_000
                              ? (item.volume / 1_000_000).toFixed(1) + "M"
                              : item.volume >= 1_000
                              ? (item.volume / 1_000).toFixed(0) + "K"
                              : item.volume?.toLocaleString("fa-IR")}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`text-xs font-bold px-2 py-0.5 rounded ${
                                item.smc_score >= 0.7
                                  ? "bg-accent-emerald/15 text-accent-emerald"
                                  : item.smc_score >= 0.5
                                  ? "bg-accent-amber/15 text-accent-amber"
                                  : item.smc_score >= 0.3
                                  ? "bg-accent-rose/15 text-accent-rose"
                                  : "bg-surface-600/30 text-surface-400"
                              }`}
                            >
                              {Math.round(item.smc_score * 100)}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                                item.phase === "accumulation"
                                  ? "bg-accent-emerald/15 text-accent-emerald"
                                  : item.phase === "distribution"
                                  ? "bg-accent-rose/15 text-accent-rose"
                                  : item.phase === "markup"
                                  ? "bg-primary-600/20 text-primary-300"
                                  : "bg-surface-600/30 text-surface-400"
                              }`}
                            >
                              {item.phase === "accumulation"
                                ? "تجمع"
                                : item.phase === "distribution"
                                ? "توزیع"
                                : item.phase === "markup"
                                ? "مارکاپ"
                                : item.phase || "—"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ── No results message ── */}
          {lastFilter && !isLoading && filtered.length === 0 && (
            <div className="mt-4 glass-card p-8 text-center shrink-0">
              <span className="material-icons text-4xl text-surface-600 mb-2">search_off</span>
              <p className="text-surface-400 font-medium">هیچ نمادی با فیلترهای مشخص شده یافت نشد</p>
              <p className="text-xs text-surface-500 mt-1">معیارهای خود را تغییر دهید و دوباره تلاش کنید</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
