"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import FloatingAssistant from "@/components/FloatingAssistant";
import ErrorBoundary from "@/components/ErrorBoundary";

// ── Types ────────────────────────────────────────────────────────────────────

interface FilterCriterion {
  field: string;
  label: string;
  operator: string;
  value: number | string;
  value_to?: number | string;
}

interface ScreenedItem {
  symbol: string;
  name: string;
  market: string;
  industry: string;
  last_price: number;
  change_pct: number;
  volume: number;
  value: number;
  smc_score: number;
  phase: string;
  rank: number;
  reason: string;
  pe_ratio?: number | null;
  eps?: number | null;
  market_value?: number | null;
  liquidity_score?: number;
  power_score?: number;
  structure_score?: number;
  orderflow_score?: number;
  trigger_score?: number;
}

interface ScreenerFilterStats {
  total: number;
  avg_smc: number;
  avg_liquidity: number;
  avg_power: number;
  avg_change_pct: number;
  high_score_count: number;
  phase_distribution: Record<string, number>;
  top_industry: string;
  top_industry_count: number;
}

interface FilterResponse {
  items: ScreenedItem[];
  total: number;
  stats: ScreenerFilterStats;
  applied_filters: FilterCriterion[];
}

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  data?: Record<string, unknown>;
  count?: number;
}

interface AIReport {
  symbol: string;
  name?: string | null;
  industry?: string | null;
  text: string;
  model?: Record<string, unknown> | null;
  signal?: Record<string, unknown> | null;
  profile?: Record<string, unknown> | null;
}

// ── Filter field definitions ──────────────────────────────────────────────────

const FILTER_FIELDS = [
  { field: "smc_score", label: "SMC Score", unit: "%", min: 0, max: 100, step: 5 },
  { field: "change_pct", label: "تغییرات قیمت", unit: "%", min: -20, max: 20, step: 1 },
  { field: "volume", label: "حجم معاملات", unit: "", min: 0, max: 100_000_000, step: 100_000 },
  { field: "value", label: "ارزش معاملات", unit: "ریال", min: 0, max: 1_000_000_000_000, step: 1_000_000 },
  { field: "liquidity_score", label: "نقدشوندگی", unit: "%", min: 0, max: 100, step: 5 },
  { field: "power_score", label: "قدرت خرید", unit: "%", min: 0, max: 100, step: 5 },
  { field: "structure_score", label: "ساختار قیمت", unit: "%", min: 0, max: 100, step: 5 },
  { field: "orderflow_score", label: "جریان سفارش", unit: "%", min: 0, max: 100, step: 5 },
  { field: "trigger_score", label: "آمادگی شکست", unit: "%", min: 0, max: 100, step: 5 },
  { field: "pe_ratio", label: "P/E", unit: "", min: 0, max: 30, step: 1 },
  { field: "eps", label: "EPS", unit: "ریال", min: 0, max: 10_000, step: 100 },
  { field: "market_value", label: "ارزش بازار", unit: "ریال", min: 0, max: 1_000_000_000_000, step: 1_000_000 },
  { field: "price_change_pct", label: "تغییرات روزانه", unit: "%", min: -10, max: 10, step: 0.5 },
];

const OPERATOR_OPTIONS = [
  { value: "gte", label: "≥ بیشتر از" },
  { value: "lte", label: "≤ کمتر از" },
  { value: "gt", label: "> بزرگتر از" },
  { value: "lt", label: "< کوچکتر از" },
  { value: "eq", label: "= مساوی" },
  { value: "between", label: "بین" },
];

const INDUSTRY_OPTIONS = [
  "خودرو و ساخت قطعات",
  "دارویی",
  "فلزات اساسی",
  "سیمان، آهک و گچ",
  "بانک و موسسات اعتباری",
  "فرآورده‌های نفتی",
  "شرکت‌های چندرشاخه‌ای",
  "سرمایه‌گذاری",
  "حمل و نقل",
  "عرضه برق، گاز، بخار",
  "بیمه و صندوق بازنشستگی",
  "مخابرات",
  "لاستیک و پلاستیک",
  "رایانه و فعالیت‌های وابسته",
  "ساخت محصولات فلزی",
  "ماشین‌آلات و تجهیزات",
  "محصولات شیمیایی",
  "غذایی و آشامیدنی",
  "کشاورزی",
  "ساخت دستگاه‌ها و وسایل ارتباطی",
];

const MARKET_OPTIONS = [
  { value: "", label: "همه بازارها" },
  { value: "BOURS", label: "بورس" },
  { value: "FARA", label: "فرابورس" },
  { value: "ENERGY", label: "انرژی" },
  { value: "COMMODITY", label: "کالا" },
];

// ── Persian numeral helpers ──────────────────────────────────────────────────

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
const ARABIC_DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

function toPersianNum(n: number): string {
  const s = String(Math.round(n));
  let out = "";
  for (const ch of s) {
    const idx = ARABIC_DIGITS.indexOf(ch);
    out += idx >= 0 ? PERSIAN_DIGITS[idx] : ch;
  }
  return out;
}

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function formatPrice(v: number): string {
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  return v.toLocaleString("fa-IR");
}

function pctScore(score: number): number {
  return Math.round(score * 100);
}

// ── Suggestion presets ───────────────────────────────────────────────────────

const PRESET_FILTERS: { name: string; filters: FilterCriterion[] }[] = [
  {
    name: "SMC قوی + نقدشوندگی بالا",
    filters: [
      { field: "smc_score", label: "SMC Score", operator: "gte", value: 0.6 },
      { field: "liquidity_score", label: "نقدشوندگی", operator: "gte", value: 0.5 },
    ],
  },
  {
    name: "پول هوشمند در حال ورود",
    filters: [
      { field: "power_score", label: "قدرت خرید", operator: "gte", value: 0.6 },
      { field: "trigger_score", label: "آمادگی شکست", operator: "gte", value: 0.5 },
    ],
  },
  {
    name: "سهام ارزنده (P/E پایین)",
    filters: [
      { field: "pe_ratio", label: "P/E", operator: "lte", value: 7 },
      { field: "smc_score", label: "SMC Score", operator: "gte", value: 0.4 },
    ],
  },
  {
    name: "پرحجم + تغییرات مثبت",
    filters: [
      { field: "volume", label: "حجم معاملات", operator: "gte", value: 5_000_000 },
      { field: "change_pct", label: "تغییرات قیمت", operator: "gte", value: 1 },
    ],
  },
  {
    name: "آماده شکست (Trigger بالا)",
    filters: [
      { field: "trigger_score", label: "آمادگی شکست", operator: "gte", value: 0.7 },
    ],
  },
  {
    name: "قدرت خرید عالی",
    filters: [
      { field: "power_score", label: "قدرت خرید", operator: "gte", value: 0.7 },
      { field: "volume", label: "حجم معاملات", operator: "gte", value: 1_000_000 },
    ],
  },
];

// ── Sidebar navigation ───────────────────────────────────────────────────────

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

// ── Phase badge helper ───────────────────────────────────────────────────────

function PhaseBadge({ phase }: { phase: string }) {
  const phaseColors: Record<string, string> = {
    accumulation: "bg-accent-emerald/15 text-accent-emerald",
    distribution: "bg-accent-rose/15 text-accent-rose",
    markup: "bg-primary-600/20 text-primary-300",
    markdown: "bg-accent-rose/20 text-accent-rose",
    neutral: "bg-surface-600/30 text-surface-400",
    confirmed_smart_money: "bg-accent-violet/20 text-accent-violet",
    breakout_ready: "bg-accent-amber/15 text-accent-amber",
    float_lock: "bg-accent-cyan/15 text-accent-cyan",
    active_absorption: "bg-primary-400/15 text-primary-300",
    early_accumulation: "bg-accent-emerald/10 text-accent-emerald",
  };
  const phaseLabels: Record<string, string> = {
    accumulation: "تجمع",
    distribution: "توزیع",
    markup: "مارکاپ",
    markdown: "مارک‌داون",
    neutral: "خنثی",
    confirmed_smart_money: "پول هوشمند تأیید شده",
    breakout_ready: "آماده شکست",
    float_lock: "قفل شناور",
    active_absorption: "جذب فعال",
    early_accumulation: "تجمع اولیه",
  };
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
        phaseColors[phase] || phaseColors.neutral
      }`}
    >
      {phaseLabels[phase] || phase}
    </span>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const pct = pctScore(score);
  let color: string;
  if (score >= 0.7) color = "bg-accent-emerald/15 text-accent-emerald";
  else if (score >= 0.5) color = "bg-accent-amber/15 text-accent-amber";
  else if (score >= 0.3) color = "bg-accent-rose/15 text-accent-rose";
  else color = "bg-surface-600/30 text-surface-400";
  return <span className={`text-xs font-bold px-2 py-0.5 rounded ${color}`}>{pct}</span>;
}

// ── Main Component ───────────────────────────────────────────────────────────

function SmartScreenerPageInner() {
  // ── State ──
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "به غربالگر هوشمند بازار سرمایه خوش آمدید.\n\nمی‌توانید با فیلترهای بصری یا تایپ سوال، نمادهای مورد نظر خود را پیدا کنید.\nبیش از ۱۵ پارامتر تکنیکال و بنیادی قابل فیلتر است.",
    },
  ]);
  const [input, setInput] = useState("");
  const [filters, setFilters] = useState<FilterCriterion[]>([]);
  const [filterLogic, setFilterLogic] = useState<"and" | "or">("and");
  const [marketFilter, setMarketFilter] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState("smc_score");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [showFilterBuilder, setShowFilterBuilder] = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const [expandedStats, setExpandedStats] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // New filter form state
  const [newField, setNewField] = useState("smc_score");
  const [newOperator, setNewOperator] = useState("gte");
  const [newValue, setNewValue] = useState("");
  const [newValueTo, setNewValueTo] = useState("");

  const [defaultLimit, setDefaultLimit] = useState(50);

  // ── Data fetch ──
  const queryKey = JSON.stringify({ filters, filterLogic, marketFilter, minScore, sortBy, sortOrder });

  const { data: filterResponse, isLoading, isError: isFilterError, error: filterError, refetch: refetchFilter } = useQuery({
    queryKey: ["smart-screener-filter", queryKey],
    queryFn: async () => {
      const payload = {
        filters: filters.map((f) => ({
          field: f.field,
          operator: f.operator,
          value: f.value,
          ...(f.value_to !== undefined ? { value_to: f.value_to } : {}),
        })),
        logic: filterLogic,
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: 500,
        market: marketFilter || undefined,
        min_score: minScore / 100,
        include_details: true,
      };
      const res = await apiPost<{ success: boolean; data: FilterResponse; error?: { message: string } }>("/screener/filter", payload);
      if (!res?.success) {
        throw new Error(res?.error?.message || "خطا در دریافت نتایج");
      }
      return res?.data ?? { items: [], total: 0, stats: {} as ScreenerFilterStats, applied_filters: [] };
    },
    enabled: filters.length > 0,
    refetchInterval: 120_000,
    retry: 2,
  });

  const { data: defaultData, isLoading: isDefaultLoading, isError: isDefaultError, error: defaultError, refetch: refetchDefault } = useQuery({
    queryKey: ["smart-screener-default", defaultLimit],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("sort_by", "smc_score");
      params.set("sort_order", "desc");
      params.set("limit", String(defaultLimit));
      const res = await apiGet<{ success: boolean; data: { items: ScreenedItem[]; total: number }; error?: { message: string } }>(
        `/screener?${params.toString()}`
      );
      if (!res?.success) {
        throw new Error(res?.error?.message || "خطا در دریافت داده‌های بازار");
      }
      return res?.data ?? { items: [], total: 0 };
    },
    enabled: filters.length === 0,
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: 2,
  });

  const apiError = isFilterError ? (filterError instanceof Error ? filterError.message : "خطایی رخ داد") :
                   isDefaultError ? (defaultError instanceof Error ? defaultError.message : "خطایی رخ داد") :
                   null;
  const isAnyLoading = isLoading || isDefaultLoading;

  // ── Staggered loading: first batch loads immediately, then expand to full ──
  useEffect(() => {
    if (!isDefaultLoading && defaultLimit === 50 && defaultData && (defaultData.items?.length ?? 0) > 0) {
      const timer = setTimeout(() => {
        setDefaultLimit(500);
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [isDefaultLoading, defaultLimit, defaultData]);

  const items = filterResponse?.items ?? defaultData?.items ?? [];
  const stats = filterResponse?.stats;
  const hasActiveFilters = filters.length > 0;

  // ── Chat assistant API ──
  const assistantMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await apiPost<{ success: boolean; data: { text: string; type: string; data?: Record<string, unknown> } }>(
        "/stock-assistant/query", { message }
      );
      return res;
    },
    onSuccess: (res, variables) => {
      const data = res?.data;
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: data?.text ?? "پاسخی دریافت نشد.",
        data: data?.data as Record<string, unknown> | undefined,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    },
    onError: () => {
      setMessages((prev) => [...prev, {
        id: `a-${Date.now()}`,
        role: "assistant",
        text: "خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.",
      }]);
    },
  });

  // ── AI report modal state ──
  const [aiReportSymbol, setAiReportSymbol] = useState<string | null>(null);
  const [aiReport, setAiReport] = useState<AIReport | null>(null);
  const [aiReportLoading, setAiReportLoading] = useState(false);
  const [aiReportError, setAiReportError] = useState<string | null>(null);

  const openAiReport = useCallback(async (symbol: string) => {
    setAiReportSymbol(symbol);
    setAiReport(null);
    setAiReportError(null);
    setAiReportLoading(true);
    try {
      const res = await apiGet<{ success: boolean; data: AIReport; error?: { message: string } }>(
        `/screener110/report/${encodeURIComponent(symbol)}`
      );
      if (!res?.success) {
        throw new Error(res?.error?.message || "خطا در دریافت گزارش");
      }
      setAiReport(res.data ?? null);
    } catch (err) {
      setAiReportError(err instanceof Error ? err.message : "خطا در دریافت گزارش");
    } finally {
      setAiReportLoading(false);
    }
  }, []);

  // ── Filter management ──
  const addFilter = useCallback(() => {
    const fieldDef = FILTER_FIELDS.find((f) => f.field === newField);
    if (!fieldDef) return;
    const val = parseFloat(newValue);
    if (isNaN(val)) return;

    const criterion: FilterCriterion = {
      field: newField,
      label: fieldDef.label,
      operator: newOperator,
      value: val,
    };
    if (newOperator === "between") {
      const valTo = parseFloat(newValueTo);
      if (!isNaN(valTo)) criterion.value_to = valTo;
    }
    setFilters((prev) => [...prev, criterion]);
    setNewValue("");
    setNewValueTo("");
  }, [newField, newOperator, newValue, newValueTo]);

  const removeFilter = useCallback((index: number) => {
    setFilters((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters([]);
    setMarketFilter("");
    setMinScore(0);
    setSortBy("smc_score");
    setSortOrder("desc");
    setDefaultLimit(20);  // reset staggered loading
  }, []);

  const applyPreset = useCallback((preset: typeof PRESET_FILTERS[number]) => {
    setFilters(preset.filters);
    setShowPresets(false);
    setShowFilterBuilder(false);
  }, []);

  // ── Submit chat query ──
  const handleSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      const userMsg: Message = { id: `u-${Date.now()}`, role: "user", text: trimmed };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      assistantMutation.mutate(trimmed);
    },
    [assistantMutation]
  );

  // ── Export Excel ──
  const exportExcel = useCallback(async () => {
    if (items.length === 0) return;
    try {
      // SheetJS is bundled locally (package.json: xlsx) — dynamic import keeps
      // it code-split (no eval, no eager ~1MB bundle on page load).
      const XLSX = await import("xlsx");
      const headers = [["نماد", "نام", "صنعت", "قیمت", "تغییرات%", "حجم", "SMC", "فاز", "P/E", "EPS", "محصول"]];
      const data = items.slice(0, 200).map((item) => [
        item.symbol,
        item.name,
        item.industry || "",
        item.last_price ?? 0,
        item.change_pct ?? 0,
        item.volume ?? 0,
        Math.round((item.smc_score ?? 0) * 100),
        item.phase ?? "",
        item.pe_ratio ?? "",
        item.eps ?? "",
        item.reason || "",
      ]);

      const ws = XLSX.utils.aoa_to_sheet([...headers, ...data]);

      // Set column widths
      ws["!cols"] = [
        { wch: 12 }, { wch: 22 }, { wch: 18 }, { wch: 14 },
        { wch: 10 }, { wch: 14 }, { wch: 6 }, { wch: 14 },
        { wch: 8 }, { wch: 10 }, { wch: 20 },
      ];

      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Screener");

      const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      const blob = new Blob([wbout], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `screener_results_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Excel export failed:", err);
      // Fallback to CSV
      const headers = ["نماد", "نام", "صنعت", "قیمت", "تغییرات%", "حجم", "SMC", "فاز", "P/E", "EPS"];
      const rows = items.slice(0, 200).map((item) => [
        item.symbol,
        item.name,
        item.industry,
        item.last_price?.toLocaleString("fa-IR") ?? "",
        (item.change_pct ?? 0).toFixed(2),
        formatVolume(item.volume ?? 0),
        pctScore(item.smc_score ?? 0).toString(),
        item.phase ?? "",
        item.pe_ratio?.toString() ?? "",
        item.eps?.toLocaleString("fa-IR") ?? "",
      ]);
      const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `screener_results_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [items]);

  // ── Auto-focus ──
  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, items]);

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
                onClick={() => setShowPresets(!showPresets)}
                className="flex items-center gap-2 px-3 py-2 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-xs font-medium transition-all"
              >
                <span className="material-icons text-sm">bookmark</span>
                پریست‌ها
              </button>
              <button
                onClick={() => setShowFilterBuilder(!showFilterBuilder)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  showFilterBuilder || hasActiveFilters
                    ? "bg-primary-600 text-white"
                    : "bg-surface-800 text-surface-300 hover:bg-surface-700"
                }`}
              >
                <span className="material-icons text-sm">tune</span>
                فیلتر {hasActiveFilters ? `(${filters.length})` : ""}
              </button>
              <button
                onClick={() => {
                  setMessages([{ id: "welcome", role: "assistant", text: "فیلتر جدیدی اعمال کنید." }]);
                  clearFilters();
                }}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-sm font-medium transition-all"
              >
                <span className="material-icons text-sm">add</span>
                جدید
              </button>
            </div>
          </div>

          {/* ── Presets dropdown ── */}
          {showPresets && (
            <div className="mb-3 glass-card p-3">
              <p className="text-xs text-surface-500 mb-2">فیلترهای آماده:</p>
              <div className="flex flex-wrap gap-2">
                {PRESET_FILTERS.map((preset, i) => (
                  <button
                    key={i}
                    onClick={() => applyPreset(preset)}
                    className="px-3 py-1.5 bg-surface-800 hover:bg-primary-600/20 text-surface-300 hover:text-primary-300 rounded-lg text-xs transition-all border border-surface-700 hover:border-primary-500/30"
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── Visual Filter Builder ── */}
          {showFilterBuilder && (
            <div className="mb-3 glass-card p-4">
              {/* Active filters */}
              {hasActiveFilters && (
                <div className="mb-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-surface-400">فیلترهای فعال:</span>
                    <select
                      value={filterLogic}
                      onChange={(e) => setFilterLogic(e.target.value as "and" | "or")}
                      className="px-2 py-0.5 bg-surface-800 border border-surface-700 rounded text-xs text-surface-300"
                    >
                      <option value="and">همه (AND)</option>
                      <option value="or">حداقل یکی (OR)</option>
                    </select>
                    <button onClick={clearFilters} className="text-xs text-accent-rose hover:text-accent-rose/80 mr-auto">
                      پاک کردن همه
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {filters.map((f, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-primary-600/10 border border-primary-600/20 rounded-lg text-xs text-primary-300"
                      >
                        <span>{f.label}</span>
                        <span className="text-surface-500">
                          {OPERATOR_OPTIONS.find((o) => o.value === f.operator)?.label.split(" ")[0] || f.operator}
                        </span>
                        <span className="font-mono font-bold">{f.value}</span>
                        {f.value_to !== undefined && (
                          <span className="font-mono font-bold">- {f.value_to}</span>
                        )}
                        <button onClick={() => removeFilter(i)} className="text-surface-500 hover:text-accent-rose mr-1">
                          <span className="material-icons text-xs">close</span>
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Add new filter */}
              <div className="flex items-end gap-2 flex-wrap">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-surface-500">پارامتر</label>
                  <select
                    value={newField}
                    onChange={(e) => {
                      setNewField(e.target.value);
                      setNewValue("");
                      setNewValueTo("");
                    }}
                    className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-xs text-surface-200 focus:outline-none focus:border-primary-500"
                  >
                    {FILTER_FIELDS.map((f) => (
                      <option key={f.field} value={f.field}>{f.label}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-surface-500">عملگر</label>
                  <select
                    value={newOperator}
                    onChange={(e) => setNewOperator(e.target.value)}
                    className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-xs text-surface-200 focus:outline-none focus:border-primary-500"
                  >
                    {OPERATOR_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-surface-500">مقدار</label>
                  <input
                    type="number"
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    placeholder="مقدار..."
                    className="w-24 px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-xs text-surface-200 focus:outline-none focus:border-primary-500"
                  />
                </div>
                {newOperator === "between" && (
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-surface-500">تا</label>
                    <input
                      type="number"
                      value={newValueTo}
                      onChange={(e) => setNewValueTo(e.target.value)}
                      placeholder="تا..."
                      className="w-24 px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-xs text-surface-200 focus:outline-none focus:border-primary-500"
                    />
                  </div>
                )}
                <button
                  onClick={addFilter}
                  disabled={!newValue}
                  className="px-4 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-lg text-xs transition-all"
                >
                  <span className="material-icons text-sm">add</span>
                </button>
              </div>

              {/* Market filter + sort */}
              <div className="flex items-center gap-3 mt-3 flex-wrap">
                <div className="flex gap-1">
                  {MARKET_OPTIONS.map((m) => (
                    <button
                      key={m.value}
                      onClick={() => setMarketFilter(m.value)}
                      className={`px-2 py-1 rounded-lg text-[10px] font-medium transition-all ${
                        marketFilter === m.value
                          ? "bg-primary-600 text-white"
                          : "bg-surface-800 text-surface-400 hover:text-surface-200"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-surface-500">SMC:</span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={minScore}
                    onChange={(e) => setMinScore(Number(e.target.value))}
                    className="w-16 accent-primary-500"
                  />
                  <span className="text-xs font-mono text-surface-300 w-8">{minScore}%</span>
                </div>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="px-2 py-1 bg-surface-800 border border-surface-700 rounded text-xs text-surface-300"
                >
                  <option value="smc_score">SMC</option>
                  <option value="change_pct">تغییرات</option>
                  <option value="volume">حجم</option>
                  <option value="liquidity_score">نقدشوندگی</option>
                  <option value="power_score">قدرت خرید</option>
                  <option value="trigger_score">تریگر</option>
                </select>
                <button
                  onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
                  className="px-2 py-1 bg-surface-800 border border-surface-700 rounded text-xs text-surface-300 hover:bg-surface-700"
                >
                  {sortOrder === "desc" ? "⬇ نزولی" : "⬆ صعودی"}
                </button>
              </div>
            </div>
          )}

          {/* ── Two-column layout: Chat + Results ── */}
          <div className="flex-1 flex gap-4 min-h-0">
            {/* ── Chat column ── */}
            <div className="flex flex-col w-96 shrink-0">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto space-y-3 mb-3 px-1">
                {messages.map((msg) => (
                  <div key={msg.id} className="flex justify-start">
                    <div
                      className={`max-w-[90%] rounded-2xl p-3 ${
                        msg.role === "user"
                          ? "bg-primary-600/20 border border-primary-600/20 text-surface-200 rounded-br-md"
                          : "glass-card rounded-bl-md"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="material-icons text-primary-400 text-sm">
                          {msg.role === "user" ? "person" : "smart_toy"}
                        </span>
                        <span className="text-[10px] text-surface-500 font-bold">
                          {msg.role === "user" ? "شما" : "غربالگر هوشمند"}
                        </span>
                      </div>
                      <div className="text-xs text-surface-300 leading-relaxed whitespace-pre-wrap">
                        {msg.text}
                      </div>
                    </div>
                  </div>
                ))}
                {assistantMutation.isPending && (
                  <div className="flex justify-start">
                    <div className="glass-card rounded-2xl rounded-bl-md p-3">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>

              {/* Suggestions */}
              {messages.length === 1 && !hasActiveFilters && (
                <div className="mb-3">
                  <p className="text-[10px] text-surface-500 mb-2 px-1">پیشنهادات — کلیک کنید:</p>
                  <div className="grid grid-cols-1 gap-1.5">
                    {[
                      { text: "سهم‌هایی با P/E کمتر از ۷ و ROE بالای ۲۰", desc: "سهام ارزنده" },
                      { text: "نمادهای با SMC بالای ۶۰", desc: "پول هوشمند" },
                      { text: "سهم‌های خودرو با حجم بالا", desc: "صنعت خودرو" },
                      { text: "شرکت‌های با قدرت خرید قوی", desc: "ورود پول" },
                    ].map((s, i) => (
                      <button
                        key={i}
                        onClick={() => handleSubmit(s.text)}
                        className="glass-card p-2 flex items-center gap-2 hover:bg-white/[0.03] transition-all text-right group"
                      >
                        <span className="material-icons text-surface-600 group-hover:text-primary-400 transition-colors text-sm">chat</span>
                        <span className="text-xs text-surface-400 group-hover:text-surface-200 transition-colors">{s.text}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Chat input */}
              <div className="glass-card p-2 flex items-center gap-2 shrink-0">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleSubmit(input); } }}
                  placeholder="سوال خود را بپرسید..."
                  className="flex-1 bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 text-xs text-surface-200 outline-none focus:border-primary-500 placeholder:text-surface-600"
                />
                <button
                  onClick={() => handleSubmit(input)}
                  disabled={!input.trim()}
                  className="p-2 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl transition-all"
                >
                  <span className="material-icons text-sm">send</span>
                </button>
              </div>
            </div>

            {/* ── Results column ── */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Loading */}
              {isAnyLoading && (
                <div className="flex items-center gap-2 text-xs text-surface-500 mb-2">
                  <span className="w-2 h-2 bg-primary-400 rounded-full animate-pulse" />
                  در حال بارگذاری...
                  {defaultLimit < 50 && isDefaultLoading && (
                    <span className="text-surface-600">(دسته اول: {defaultLimit} نماد)</span>
                  )}
                  {defaultLimit >= 50 && isDefaultLoading && (
                    <span className="text-surface-600">(در حال بارگذاری کامل...)</span>
                  )}
                </div>
              )}

              {/* API Error banner */}
              {apiError && (
                <div className="mb-3 glass-card p-3 border border-accent-rose/30 bg-accent-rose/5">
                  <div className="flex items-start gap-2">
                    <span className="material-icons text-accent-rose text-sm mt-0.5">error_outline</span>
                    <div className="flex-1">
                      <p className="text-xs font-bold text-accent-rose mb-1">خطا در دریافت داده</p>
                      <p className="text-[10px] text-surface-400 leading-relaxed">{apiError}</p>
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => hasActiveFilters ? refetchFilter() : refetchDefault()}
                          className="px-3 py-1 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg text-[10px] transition-all"
                        >
                          <span className="material-icons text-xs mr-1">refresh</span>
                          تلاش مجدد
                        </button>
                        {hasActiveFilters && (
                          <button
                            onClick={clearFilters}
                            className="px-3 py-1 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg text-[10px] transition-all"
                          >
                            پاک کردن فیلترها
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Stats cards */}
              {hasActiveFilters && stats && stats.total > 0 && (
                <div className="mb-3">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="glass-card p-2 text-center">
                      <p className="text-lg font-black text-surface-100">{toPersianNum(stats.total)}</p>
                      <p className="text-[10px] text-surface-500">نماد فیلتر شده</p>
                    </div>
                    <div className="glass-card p-2 text-center">
                      <p className="text-lg font-black text-accent-emerald">{toPersianNum(stats.high_score_count)}</p>
                      <p className="text-[10px] text-surface-500">SMC ≥ ۶۰%</p>
                    </div>
                    <div className="glass-card p-2 text-center">
                      <p className="text-lg font-black text-surface-100">{(stats.avg_smc * 100).toFixed(0)}%</p>
                      <p className="text-[10px] text-surface-500">میانگین SMC</p>
                    </div>
                    <div className="glass-card p-2 text-center">
                      <p className="text-lg font-black text-primary-300">{(stats.avg_liquidity * 100).toFixed(0)}%</p>
                      <p className="text-[10px] text-surface-500">میانگین نقدشوندگی</p>
                    </div>
                  </div>

                  {/* Phase distribution + expanded stats */}
                  <button
                    onClick={() => setExpandedStats(!expandedStats)}
                    className="text-[10px] text-primary-400 hover:text-primary-300 mt-1 flex items-center gap-1"
                  >
                    <span className="material-icons text-xs">{expandedStats ? "expand_less" : "expand_more"}</span>
                    {expandedStats ? "بستن جزئیات" : "جزئیات بیشتر"}
                  </button>

                  {expandedStats && (
                    <div className="glass-card p-3 mt-2">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div>
                          <p className="text-[10px] text-surface-500 mb-1">توزیع فازها</p>
                          <div className="space-y-1">
                            {Object.entries(stats.phase_distribution).map(([phase, count]) => (
                              <div key={phase} className="flex items-center justify-between text-xs">
                                <PhaseBadge phase={phase} />
                                <span className="font-mono text-surface-400">{count}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="text-[10px] text-surface-500 mb-1">میانگین‌ها</p>
                          <div className="space-y-1 text-xs">
                            <div className="flex justify-between"><span className="text-surface-400">قدرت خرید</span><span className="font-mono text-surface-200">{(stats.avg_power * 100).toFixed(0)}%</span></div>
                            <div className="flex justify-between"><span className="text-surface-400">تغییرات</span><span className="font-mono text-surface-200">{stats.avg_change_pct.toFixed(2)}%</span></div>
                            {stats.top_industry && (
                              <div className="flex justify-between"><span className="text-surface-400">صنعت برتر</span><span className="font-mono text-surface-200">{stats.top_industry} ({stats.top_industry_count})</span></div>
                            )}
                          </div>
                        </div>
                        <div className="col-span-2">
                          <p className="text-[10px] text-surface-500 mb-1">محدوده SMC</p>
                          <div className="h-6 bg-surface-800 rounded-full overflow-hidden flex">
                            {(() => {
                              const total = stats.total || 1;
                              const high = (stats.high_score_count / total) * 100;
                              const mid = ((stats.total - stats.high_score_count - 0) / total) * 100;
                              const low = 0;
                              return (
                                <>
                                  <div className="bg-accent-emerald/50 h-full transition-all" style={{ width: `${high}%` }} title="SMC ≥ 60%" />
                                  <div className="bg-accent-amber/40 h-full transition-all" style={{ width: `${mid}%` }} title="SMC 30-60%" />
                                  <div className="bg-accent-rose/30 h-full transition-all" style={{ width: `${Math.max(low, 1)}%` }} title="SMC < 30%" />
                                </>
                              );
                            })()}
                          </div>
                          <div className="flex justify-between text-[10px] text-surface-500 mt-1">
                            <span>≥ ۶۰% ({stats.high_score_count})</span>
                            <span>۳۰-۶۰% ({stats.total - stats.high_score_count})</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Results table */}
              {items.length > 0 ? (
                <div className="flex-1 glass-card overflow-hidden flex flex-col">
                  {/* Table toolbar */}
                  <div className="px-4 py-2 border-b border-surface-700/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-surface-400">
                        {toPersianNum(items.length)} نماد
                        {hasActiveFilters && <span className="text-surface-500 mr-1">(فیلتر شده)</span>}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={exportExcel}
                        className="flex items-center gap-1 px-2.5 py-1.5 bg-accent-emerald/10 hover:bg-accent-emerald/20 text-accent-emerald rounded-lg text-[10px] transition-all border border-accent-emerald/20"
                      >
                        <span className="material-icons text-xs">table_chart</span>
                        Excel
                      </button>
                    </div>
                  </div>

                  {/* Table */}
                  <div className="flex-1 overflow-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-surface-900/95 backdrop-blur z-10">
                        <tr className="border-b border-surface-700/50">
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400">#</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400">نماد</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400 hidden md:table-cell">نام</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400 hidden lg:table-cell">صنعت</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400">قیمت</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400">تغییرات</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400 hidden sm:table-cell">حجم</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400">SMC</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400 hidden sm:table-cell">فاز</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400 hidden xl:table-cell">P/E</th>
                          <th className="px-3 py-2 text-right text-[10px] font-medium text-surface-400"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item, i) => (
                          <tr
                            key={`${item.symbol}-${i}`}
                            className="border-b border-surface-800/30 hover:bg-white/[0.02] transition-colors cursor-pointer"
                            onClick={() => { window.location.href = `/symbol/${encodeURIComponent(item.symbol)}`; }}
                          >
                            <td className="px-3 py-2 text-surface-500 font-mono text-[10px]">{toPersianNum(i + 1)}</td>
                            <td className="px-3 py-2">
                              <span className="font-bold text-primary-300 hover:text-primary-200 text-xs">{item.symbol}</span>
                            </td>
                            <td className="px-3 py-2 text-surface-300 text-[10px] max-w-[100px] truncate hidden md:table-cell">{item.name}</td>
                            <td className="px-3 py-2 text-surface-500 text-[10px] hidden lg:table-cell">{item.industry || "—"}</td>
                            <td className="px-3 py-2 font-mono text-surface-200 text-[11px]">{item.last_price?.toLocaleString("fa-IR")}</td>
                            <td className="px-3 py-2">
                              <span className={`font-mono text-[11px] font-medium ${(item.change_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                                {(item.change_pct ?? 0) >= 0 ? "+" : ""}{item.change_pct?.toFixed(2)}%
                              </span>
                            </td>
                            <td className="px-3 py-2 font-mono text-surface-400 text-[10px] hidden sm:table-cell">{formatVolume(item.volume ?? 0)}</td>
                            <td className="px-3 py-2"><ScoreBadge score={item.smc_score ?? 0} /></td>
                            <td className="px-3 py-2 hidden sm:table-cell"><PhaseBadge phase={item.phase ?? ""} /></td>
                            <td className="px-3 py-2 font-mono text-surface-400 text-[10px] hidden xl:table-cell">{item.pe_ratio?.toFixed(1) ?? "—"}</td>
                            <td className="px-3 py-2">
                              <button
                                onClick={(e) => { e.stopPropagation(); openAiReport(item.symbol); }}
                                title="گزارش هوشمند AI"
                                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium bg-primary-600/10 hover:bg-primary-600/25 text-primary-300 hover:text-primary-200 border border-primary-600/20 transition-all"
                              >
                                <span className="material-icons text-xs">psychology_alt</span>
                                <span className="hidden xl:inline">گزارش AI</span>
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                /* Empty state */
                <div className="flex-1 glass-card p-8 text-center flex items-center justify-center">
                  <div>
                    {isDefaultLoading ? (
                      <>
                        <div className="inline-flex items-center gap-2 mb-2">
                          <span className="w-3 h-3 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="w-3 h-3 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="w-3 h-3 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                        <p className="text-surface-400 font-medium text-sm">در حال بارگذاری داده‌ها...</p>
                        <p className="text-[10px] text-surface-500 mt-1">لطفاً چند لحظه صبر کنید</p>
                      </>
                    ) : apiError ? (
                  <>
                    <span className="material-icons text-5xl text-accent-rose/50 mb-3">cloud_off</span>
                    <p className="text-accent-rose font-medium text-sm">خطا در ارتباط با سرور</p>
                    <p className="text-[10px] text-surface-500 mt-1 max-w-md">
                      {apiError}
                    </p>
                    <div className="flex justify-center gap-2 mt-4">
                      <button
                        onClick={() => refetchDefault()}
                        className="px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-xs transition-all"
                      >
                        <span className="material-icons text-sm mr-1">refresh</span>
                        تلاش مجدد
                      </button>
                    </div>
                  </>
                ) : (
                      <>
                        <span className="material-icons text-5xl text-surface-600 mb-3">search</span>
                        <p className="text-surface-400 font-medium text-sm">
                          {hasActiveFilters ? "هیچ نمادی با این فیلترها یافت نشد" : "برای شروع یک فیلتر انتخاب کنید"}
                        </p>
                        <p className="text-[10px] text-surface-500 mt-1">
                          {hasActiveFilters ? "مقادیر فیلترها را تغییر دهید" : "از دکمه فیلتر یا پریست‌ها استفاده کنید"}
                        </p>
                        {!hasActiveFilters && (
                          <div className="flex justify-center gap-2 mt-4">
                            <button
                              onClick={() => refetchDefault()}
                              className="px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-xs transition-all"
                            >
                              <span className="material-icons text-sm mr-1">trending_up</span>
                              نمایش برترین‌ها
                            </button>
                            <button
                              onClick={() => setShowFilterBuilder(true)}
                              className="px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-xs transition-all"
                            >
                              باز کردن فیلتر
                            </button>
                            <button
                              onClick={() => setShowPresets(true)}
                              className="px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-xs transition-all"
                            >
                              پریست‌ها
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
      {/* ── AI Report Modal ── */}
      {aiReportSymbol && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setAiReportSymbol(null)}
        >
          <div
            className="glass-card w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center gap-2 px-5 py-3 border-b border-surface-700/50 bg-surface-900/60">
              <span className="material-icons text-primary-400">psychology_alt</span>
              <span className="font-bold text-sm text-surface-100">گزارش هوشمند {aiReportSymbol}</span>
              <button
                onClick={() => setAiReportSymbol(null)}
                className="mr-auto p-1.5 rounded-lg hover:bg-white/5 text-surface-400 hover:text-surface-200 transition-all"
              >
                <span className="material-icons text-lg">close</span>
              </button>
            </div>

            {/* Modal body */}
            <div className="flex-1 overflow-y-auto p-5">
              {aiReportLoading && (
                <div className="flex flex-col items-center gap-3 py-12">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <p className="text-xs text-surface-400">در حال تحلیل {aiReportSymbol} با مدل ۱۱۰ ستونی...</p>
                </div>
              )}

              {aiReportError && !aiReportLoading && (
                <div className="glass-card p-4 border border-accent-rose/30 bg-accent-rose/5">
                  <p className="text-xs font-bold text-accent-rose mb-1">خطا در دریافت گزارش</p>
                  <p className="text-[10px] text-surface-400">{aiReportError}</p>
                </div>
              )}

              {aiReport && !aiReportLoading && (
                <div className="text-xs text-surface-200 leading-relaxed whitespace-pre-wrap font-[inherit]" dir="rtl">
                  {aiReport.text}
                </div>
              )}

              {!aiReport && !aiReportLoading && !aiReportError && (
                <p className="text-xs text-surface-500 py-8 text-center">داده‌ای موجود نیست.</p>
              )}
            </div>

            {/* Modal footer */}
            <div className="flex items-center gap-2 px-5 py-3 border-t border-surface-700/50 bg-surface-900/60">
              <a
                href={`/symbol/${encodeURIComponent(aiReportSymbol)}`}
                className="flex items-center gap-1.5 px-3 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-xs font-medium transition-all"
              >
                <span className="material-icons text-sm">show_chart</span>
                صفحه نماد
              </a>
              <button
                onClick={() => setAiReportSymbol(null)}
                className="px-3 py-2 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-xs transition-all"
              >
                بستن
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Assistant */}
      <FloatingAssistant />
    </div>
  );
}

export default function SmartScreenerPage() {
  return (
    <ErrorBoundary pageTitle="غربالگر هوشمند بازار سرمایه">
      <SmartScreenerPageInner />
    </ErrorBoundary>
  );
}
