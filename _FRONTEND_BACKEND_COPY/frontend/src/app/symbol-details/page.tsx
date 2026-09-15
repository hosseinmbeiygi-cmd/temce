"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ------ Types -------------------------------------------------------------------------------------------------------

interface SymbolDetail {
  ins_id: string;
  instrument_id: string | null;
  symbol: string;
  name: string | null;
  name_en: string | null;
  isin: string | null;
  code_12: string | null;
  code_5: string | null;
  code_4: string | null;
  market: string | null;
  board: string | null;
  board_id: string | null;
  board_code: string | null;
  sector: string | null;
  sector_id: number | null;
  sub_sector: string | null;
  sub_sector_id: number | null;
  shares_count: number | null;
  shares_issued: number | null;
  base_volume: number | null;
  market_value: number | null;
  free_float_pct: number | null;
  eps: number | null;
  pe_ratio: number | null;
  group_pe_ratio: number | null;
  ps_ratio: number | null;
  price_lowest_allowed: number | null;
  price_highest_allowed: number | null;
  price_min_week: number | null;
  price_max_week: number | null;
  price_min_year: number | null;
  price_max_year: number | null;
  price_min: number | null;
  price_max: number | null;
  price_yesterday: number | null;
  price_first: number | null;
  price_last: number | null;
  price_last_change: number | null;
  price_last_change_pct: number | null;
  price_close: number | null;
  price_close_change: number | null;
  price_close_change_pct: number | null;
  trade_count: number | null;
  trade_volume: number | null;
  trade_volume_avg_month: number | null;
  trade_value: number | null;
  buy_real_count: number | null;
  buy_legal_count: number | null;
  sell_real_count: number | null;
  sell_legal_count: number | null;
  buy_real_volume: number | null;
  buy_legal_volume: number | null;
  sell_real_volume: number | null;
  sell_legal_volume: number | null;
  state: string | null;
  date: string | null;
  date_update: string | null;
  time: string | null;
  assembly: unknown;
  updated_at: string | null;
}

interface PageResult {
  items: SymbolDetail[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ------ Helpers -----------------------------------------------------------------------------------------------------

function formatNum(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  return Math.round(val).toLocaleString("fa-IR");
}

function formatPrice(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  return val.toLocaleString("fa-IR");
}

function formatCompact(val: number | null | undefined): string {
  if (val == null || Number.isNaN(val)) return "—";
  const abs = Math.abs(val);
  if (abs >= 1e12) return (val / 1e12).toFixed(2) + " تریلیون";
  if (abs >= 1e9) return (val / 1e9).toFixed(1) + " میلیارد";
  if (abs >= 1e6) return (val / 1e6).toFixed(1) + " میلیون";
  if (abs >= 1e3) return (val / 1e3).toFixed(0) + " هزار";
  return val.toLocaleString("fa-IR");
}

function pctColor(pct: number | null | undefined): string {
  if (pct == null) return "text-surface-400";
  if (pct > 0) return "text-accent-emerald";
  if (pct < 0) return "text-accent-rose";
  return "text-surface-400";
}

function formatPct(pct: number | null | undefined): string {
  if (pct == null) return "—";
  return `${pct > 0 ? "+" : ""}${pct.toLocaleString("fa-IR", { maximumFractionDigits: 2 })}%`;
}

function formatRelative(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    const diffMs = Date.now() - d.getTime();
    const min = Math.floor(diffMs / 60000);
    if (min < 1) return "لحظات پیش";
    if (min < 60) return `${min} دقیقه پیش`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr} ساعت پیش`;
    const day = Math.floor(hr / 24);
    return `${day} روز پیش`;
  } catch {
    return String(dateStr).slice(0, 10);
  }
}

function StateBadge({ state }: { state: string | null }) {
  if (!state) return <span className="text-[10px] text-surface-600">—</span>;
  const color =
    state === "مجاز"
      ? "bg-accent-emerald/15 text-accent-emerald"
      : state === "ممنوع" || state === "متوقف"
        ? "bg-accent-rose/15 text-accent-rose"
        : "bg-accent-amber/15 text-accent-amber";
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${color}`}>{state}</span>;
}

// ------ Info row for the detail modal ------------------------------------------------------------------------------

function InfoRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-surface-800/50 last:border-0">
      <span className="text-xs text-surface-500">{label}</span>
      <span className={`text-xs text-surface-200 text-left ${mono ? "font-mono" : "font-medium"}`}>{value}</span>
    </div>
  );
}

// ------ Detail modal -----------------------------------------------------------------------------------------------

function DetailModal({ detail, onClose }: { detail: SymbolDetail | null; onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!detail) return null;

  const priceGroups: { title: string; rows: { label: string; value: string; mono?: boolean }[] }[] = [
    {
      title: "🏢 اطلاعات شرکت",
      rows: [
        { label: "نماد", value: detail.symbol, mono: true },
        { label: "نام لاتین", value: detail.name_en || "—" },
        { label: "ISIN", value: detail.isin || "—", mono: true },
        { label: "کد ۱۲ رقمی", value: detail.code_12 || "—", mono: true },
        { label: "کد ۵ رقمی", value: detail.code_5 || "—", mono: true },
        { label: "بازار", value: detail.market || "—" },
        { label: "تابلو", value: detail.board || "—" },
        { label: "گروه صنعت", value: detail.sector || "—" },
        { label: "زیرگروه", value: detail.sub_sector || "—" },
      ],
    },
    {
      title: "💰 ارزش‌گذاری",
      rows: [
        { label: "ارزش بازار", value: formatCompact(detail.market_value) },
        { label: "تعداد سهام", value: formatNum(detail.shares_count) },
        { label: "سهام صادرشده", value: formatNum(detail.shares_issued) },
        { label: "حجم مبنا", value: formatNum(detail.base_volume) },
        { label: "شناوری", value: detail.free_float_pct != null ? `${detail.free_float_pct.toLocaleString("fa-IR")}٪` : "—" },
        { label: "EPS", value: formatPrice(detail.eps) },
        { label: "P/E", value: detail.pe_ratio != null ? detail.pe_ratio.toLocaleString("fa-IR", { maximumFractionDigits: 2 }) : "—" },
        { label: "P/E گروه", value: detail.group_pe_ratio != null ? detail.group_pe_ratio.toLocaleString("fa-IR", { maximumFractionDigits: 2 }) : "—" },
        { label: "P/S", value: detail.ps_ratio != null ? detail.ps_ratio.toLocaleString("fa-IR", { maximumFractionDigits: 2 }) : "—" },
      ],
    },
    {
      title: "📈 قیمت و معاملات",
      rows: [
        { label: "آخرین قیمت", value: formatPrice(detail.price_last), mono: true },
        { label: "تغییر آخرین", value: formatPct(detail.price_last_change_pct), mono: true },
        { label: "قیمت پایانی", value: formatPrice(detail.price_close), mono: true },
        { label: "تغییر پایانی", value: formatPct(detail.price_close_change_pct), mono: true },
        { label: "قیمت دیروز", value: formatPrice(detail.price_yesterday), mono: true },
        { label: "اولین قیمت", value: formatPrice(detail.price_first), mono: true },
        { label: "کمترین / بیشترین", value: `${formatPrice(detail.price_min)} / ${formatPrice(detail.price_max)}` },
        { label: "حد مجاز پایین / بالا", value: `${formatPrice(detail.price_lowest_allowed)} / ${formatPrice(detail.price_highest_allowed)}` },
        { label: "کمترین هفته", value: formatPrice(detail.price_min_week) },
        { label: "بیشترین هفته", value: formatPrice(detail.price_max_week) },
        { label: "کمترین سال", value: formatPrice(detail.price_min_year) },
        { label: "بیشترین سال", value: formatPrice(detail.price_max_year) },
        { label: "تعداد معاملات", value: formatNum(detail.trade_count) },
        { label: "حجم معاملات", value: formatNum(detail.trade_volume) },
        { label: "میانگین حجم ماه", value: formatNum(detail.trade_volume_avg_month) },
        { label: "ارزش معاملات", value: formatCompact(detail.trade_value) },
      ],
    },
    {
      title: "👥 حقیقی / حقوقی",
      rows: [
        { label: "تعداد خریدار حقیقی", value: formatNum(detail.buy_real_count) },
        { label: "تعداد خریدار حقوقی", value: formatNum(detail.buy_legal_count) },
        { label: "تعداد فروشنده حقیقی", value: formatNum(detail.sell_real_count) },
        { label: "تعداد فروشنده حقوقی", value: formatNum(detail.sell_legal_count) },
        { label: "حجم خرید حقیقی", value: formatNum(detail.buy_real_volume) },
        { label: "حجم خرید حقوقی", value: formatNum(detail.buy_legal_volume) },
        { label: "حجم فروش حقیقی", value: formatNum(detail.sell_real_volume) },
        { label: "حجم فروش حقوقی", value: formatNum(detail.sell_legal_volume) },
      ],
    },
  ];

  const netLegal = (detail.buy_legal_volume ?? 0) - (detail.sell_legal_volume ?? 0);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="glass-card w-full max-w-3xl my-6 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="p-5 border-b border-surface-700/60 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-black text-surface-100">{detail.symbol}</h2>
              <StateBadge state={detail.state} />
            </div>
            <p className="text-sm text-surface-400 mt-1">{detail.name || "—"}</p>
            <div className="flex items-center gap-3 mt-2 text-xs text-surface-500 flex-wrap">
              <span>{detail.market || "—"}</span>
              {detail.board && <span>• {detail.board}</span>}
              {detail.sector && <span>• {detail.sector}</span>}
              {detail.date_update && <span>• به‌روزرسانی: {detail.date_update}</span>}
            </div>
          </div>
          <div className="text-left shrink-0">
            <div className="text-2xl font-black font-mono text-surface-100">{formatPrice(detail.price_last)}</div>
            <div className={`text-sm font-bold font-mono ${pctColor(detail.price_last_change_pct)}`}>
              {formatPct(detail.price_last_change_pct)}
            </div>
            <div className="text-[10px] text-surface-500 mt-1">آخرین به‌روزرسانی: {formatRelative(detail.updated_at)}</div>
          </div>
        </div>

        {/* Body */}
        <div className="p-5 max-h-[70vh] overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-5">
          {priceGroups.map((group) => (
            <div key={group.title} className={group.rows.length > 8 ? "md:col-span-2" : ""}>
              <h3 className="text-xs font-bold text-primary-300 mb-2">{group.title}</h3>
              <div className="rounded-xl bg-surface-800/40 p-3">
                {group.rows.map((row) => (
                  <InfoRow key={row.label} label={row.label} value={row.value} mono={row.mono} />
                ))}
              </div>
            </div>
          ))}

          {/* Net legal flow summary */}
          <div className="md:col-span-2">
            <h3 className="text-xs font-bold text-primary-300 mb-2">🧭 خلاصه جریان نهادی</h3>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-xl bg-accent-emerald/10 p-3">
                <div className="text-[10px] text-accent-emerald mb-1">خرید حقوقی</div>
                <div className="font-mono font-bold text-accent-emerald">{formatCompact(detail.buy_legal_volume)}</div>
              </div>
              <div className="rounded-xl bg-surface-800 p-3">
                <div className="text-[10px] text-surface-400 mb-1">خالص حقوقی</div>
                <div className={`font-mono font-bold ${netLegal >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {formatCompact(netLegal)}
                </div>
              </div>
              <div className="rounded-xl bg-accent-rose/10 p-3">
                <div className="text-[10px] text-accent-rose mb-1">فروش حقوقی</div>
                <div className="font-mono font-bold text-accent-rose">{formatCompact(detail.sell_legal_volume)}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-700/60 flex items-center justify-between gap-3">
          <Link
            href={`/symbol/${encodeURIComponent(detail.symbol)}`}
            className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
            onClick={onClose}
          >
            ← صفحه کامل نماد
          </Link>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-surface-700 hover:bg-surface-600 text-surface-200 rounded-lg text-sm transition-colors"
          >
            بستن (Esc)
          </button>
        </div>
      </div>
    </div>
  );
}

// ------ Main page --------------------------------------------------------------------------------------------------

const SORT_OPTIONS = [
  { value: "updated_at", label: "آخرین به‌روزرسانی" },
  { value: "symbol", label: "نماد" },
  { value: "market_value", label: "ارزش بازار" },
  { value: "trade_value", label: "ارزش معاملات" },
  { value: "price_last", label: "آخرین قیمت" },
  { value: "pe_ratio", label: "P/E" },
];

export default function SymbolDetailsPage() {
  const [q, setQ] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [market, setMarket] = useState("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<SymbolDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pageSize = 50;

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(searchInput.trim());
      setPage(1);
    }, 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const params = useMemo(() => {
    const p = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_by: sortBy,
      order,
    });
    if (q) p.set("q", q);
    if (market) p.set("market", market);
    return p.toString();
  }, [page, q, market, sortBy, order]);

  const { data: result, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["symbol-details", params],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: PageResult }>(`/brsapi/symbol-details?${params}`);
      return res?.data;
    },
    refetchInterval: 60_000,
  });

  // Distinct markets from current page (lightweight client-side filter chips)
  const markets = useMemo(() => {
    const set = new Set<string>();
    (result?.items ?? []).forEach((i) => i.market && set.add(i.market));
    return Array.from(set).sort();
  }, [result]);

  const openDetail = useCallback(
    async (sym: string) => {
      setDetailLoading(true);
      try {
        const res = await apiGet<{ success: boolean; data: SymbolDetail }>(
          `/brsapi/symbol-details/${encodeURIComponent(sym)}`
        );
        if (res?.success && res.data) setSelected(res.data);
      } catch {
        // Fall back to the row we already have from the list
        const row = result?.items.find((i) => i.symbol === sym);
        if (row) setSelected(row);
      }
      setDetailLoading(false);
    },
    [result]
  );

  const toggleOrder = () => setOrder((o) => (o === "desc" ? "asc" : "desc"));

  return (
    <AppLayout
      title="جزئیات کامل نمادها"
      subtitle="داده‌های غنی‌شده از brsapi_symbol_details — مستقیم از دیتابیس"
    >
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Toolbar */}
        <div className="glass-card p-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 text-sm">🔍</span>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="جستجوی نماد، نام فارسی یا لاتین..."
              className="w-full bg-surface-800 border border-surface-700 rounded-xl pr-9 pl-3 py-2 text-sm text-surface-100 placeholder:text-surface-500 focus:outline-none focus:border-primary-500 transition-colors"
            />
          </div>

          <select
            value={market}
            onChange={(e) => {
              setMarket(e.target.value);
              setPage(1);
            }}
            className="bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
          >
            <option value="">همه بازارها</option>
            {markets.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <button
            onClick={toggleOrder}
            className="px-3 py-2 bg-surface-800 hover:bg-surface-700 border border-surface-700 rounded-xl text-sm text-surface-300 transition-colors"
            title="تغییر جهت مرتب‌سازی"
          >
            {order === "desc" ? "⬇ نزولی" : "⬆ صعودی"}
          </button>

          <button
            onClick={() => refetch()}
            className="px-3 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-sm font-medium transition-colors flex items-center gap-1.5"
          >
            <span className={`material-icons text-sm ${isFetching ? "animate-spin" : ""}`}>refresh</span>
            بروزرسانی
          </button>
        </div>

        {/* Summary strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-surface-100">{result?.total?.toLocaleString("fa-IR") ?? "—"}</div>
            <div className="text-xs text-surface-500 mt-0.5">نماد با اطلاعات کامل</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-primary-300">{result?.items?.length ?? 0}</div>
            <div className="text-xs text-surface-500 mt-0.5">نماد در این صفحه</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-surface-100">
              {result?.total_pages?.toLocaleString("fa-IR") ?? "—"}
            </div>
            <div className="text-xs text-surface-500 mt-0.5">تعداد صفحات</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-accent-emerald">
              {(result?.items ?? []).filter((i) => (i.price_last_change_pct ?? 0) > 0).length}
            </div>
            <div className="text-xs text-surface-500 mt-0.5">مثبت در این صفحه</div>
          </div>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-accent-rose">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-lg font-medium">خطا در دریافت داده‌ها</p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm transition-colors"
            >
              تلاش مجدد
            </button>
          </div>
        ) : (
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-right text-sm min-w-[900px]">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="py-3 px-3 font-medium">نماد</th>
                  <th className="py-3 px-3 font-medium">نام شرکت</th>
                  <th className="py-3 px-3 font-medium">بازار / تابلو</th>
                  <th className="py-3 px-3 font-medium">آخرین قیمت</th>
                  <th className="py-3 px-3 font-medium">تغییر</th>
                  <th className="py-3 px-3 font-medium">ارزش بازار</th>
                  <th className="py-3 px-3 font-medium">حجم</th>
                  <th className="py-3 px-3 font-medium">P/E</th>
                  <th className="py-3 px-3 font-medium">وضعیت</th>
                  <th className="py-3 px-3 font-medium">بروزرسانی</th>
                  <th className="py-3 px-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {result?.items?.length === 0 && (
                  <tr>
                    <td colSpan={11} className="py-10 text-center text-surface-500">
                      هیچ نمادی مطابق فیلتر پیدا نشد
                    </td>
                  </tr>
                )}
                {(result?.items ?? []).map((d) => (
                  <tr
                    key={d.ins_id || d.symbol}
                    className="border-b border-surface-800/50 hover:bg-white/5 transition-colors cursor-pointer"
                    onClick={() => openDetail(d.symbol)}
                  >
                    <td className="py-2.5 px-3 font-bold text-surface-100">{d.symbol}</td>
                    <td className="py-2.5 px-3 text-surface-300 text-xs max-w-[220px] truncate">{d.name || "—"}</td>
                    <td className="py-2.5 px-3 text-xs text-surface-400">
                      {d.market || "—"}
                      {d.board ? <span className="text-surface-600"> • {d.board}</span> : null}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-surface-200">{formatPrice(d.price_last)}</td>
                    <td className={`py-2.5 px-3 font-mono text-xs ${pctColor(d.price_last_change_pct)}`}>
                      {formatPct(d.price_last_change_pct)}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-xs text-surface-300">{formatCompact(d.market_value)}</td>
                    <td className="py-2.5 px-3 font-mono text-xs text-surface-400">{formatCompact(d.trade_volume)}</td>
                    <td className="py-2.5 px-3 font-mono text-xs text-surface-300">
                      {d.pe_ratio != null ? d.pe_ratio.toLocaleString("fa-IR", { maximumFractionDigits: 1 }) : "—"}
                    </td>
                    <td className="py-2.5 px-3">
                      <StateBadge state={d.state} />
                    </td>
                    <td className="py-2.5 px-3 text-[10px] text-surface-500 whitespace-nowrap">
                      {formatRelative(d.updated_at)}
                    </td>
                    <td className="py-2.5 px-3">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openDetail(d.symbol);
                        }}
                        className="text-xs text-primary-400 hover:text-primary-300 transition-colors whitespace-nowrap"
                      >
                        جزئیات ←
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {result && result.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              قبلی
            </button>
            <span className="text-sm text-surface-400 px-3">
              صفحه {page.toLocaleString("fa-IR")} از {result.total_pages.toLocaleString("fa-IR")}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(result.total_pages, p + 1))}
              disabled={page >= result.total_pages}
              className="px-3 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              بعدی
            </button>
          </div>
        )}

        {/* Footer note */}
        <div className="text-xs text-surface-600 text-center py-2">
          منبع داده: جدول <code className="bg-surface-800 px-1.5 py-0.5 rounded text-surface-400">brsapi_symbol_details</code> —{" "}
          <Link href="/brsapi" className="text-primary-400 hover:text-primary-300">
            مدیریت سینک BrsApi ←
          </Link>
        </div>
      </div>

      {detailLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <Skeleton className="h-96 w-full max-w-3xl rounded-2xl" />
        </div>
      )}
      <DetailModal detail={selected} onClose={() => setSelected(null)} />
    </AppLayout>
  );
}
