"use client";

/**
 * 🏦 Funds desk — market-level view of every investment fund on TSE / IME.
 *
 * Eight tabs over the same universe: a market overview, the full shelf, a
 * multi-criteria screener, rankings, money flows, movers, a personal watchlist
 * and a data-health panel. All numbers come from `/funds` and `/funds/v2`.
 */

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import FundNavMiniChart, { type FundNavPoint } from "@/components/FundNavMiniChart";
import AddAlertButton from "@/components/AddAlertButton";
import FundCompareModal from "@/components/FundCompareModal";
import FundDiscoveryBanner from "@/components/FundDiscoveryBanner";
import FundMarketSyncButton from "@/components/FundMarketSyncButton";
import { TabPanel, TabStrip, useTabController, type TabGroup } from "@/components/ui/Tabs";
import { useFundCoverage, useFundList, useFundMonitoring, useFundOverview, useFundRankings, usePortfolioDiffs, rankNum, type FundRow } from "@/lib/fund-queries";
import { apiGet } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { ActionGroup } from "@/components/funds/FundForms";
import { Chip, DataTable, Empty, fmt, fmtBig, fmtDate, fmtPct, Loading, MiniMetric, Panel, SourceNote, Stat, StatGrid, toneText } from "@/components/funds/ui";
import {
  Check,
  Activity,
  ArrowLeftRight,
  Banknote,
  BarChart3,
  Filter,
  Landmark,
  LayoutDashboard,
  List,
  SearchX,
  SlidersHorizontal,
  Star,
  Store,
  Tags,
  TrendingDown,
  TrendingUp,
  Trophy,
} from "lucide-react";

const PieChartCard = dynamic(() => import("@/components/charts/PieChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});
const BarChartCard = dynamic(() => import("@/components/charts/BarChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});

// ── Tabs ────────────────────────────────────────────────────────────────────

const GROUPS: TabGroup[] = [
  {
    id: "market",
    label: "بازار صندوق‌ها",
    icon: Store,
    tabs: [
      { id: "overview", label: "نمای کلی", icon: LayoutDashboard },
      { id: "shelf", label: "قفسه صندوق‌ها", icon: List },
      { id: "screener", label: "غربالگر", icon: SlidersHorizontal },
      { id: "ranking", label: "رتبه‌بندی", icon: Trophy },
      { id: "flows", label: "جریان پول", icon: ArrowLeftRight },
      { id: "movers", label: "بیشترین تغییرات", icon: TrendingUp },
      { id: "watchlist", label: "علاقه‌مندی‌ها", icon: Star },
      { id: "data", label: "پایش داده", icon: Activity },
    ],
  },
];

const TABS = GROUPS[0].tabs;

// ── Helpers ─────────────────────────────────────────────────────────────────

const WATCH_KEY = "funds:watchlist";

function fundType(name: string, fund_type?: string): string {
  if (fund_type) return fund_type;
  const n = name || "";
  if (n.includes("کالا") || n.includes("طلا") || n.includes("نقره")) return "کالایی";
  if (n.includes("درآمد") || n.includes("ثابت") || n.includes("بانک")) return "درآمد ثابت";
  if (n.includes("اهرم")) return "اهرمی";
  if (n.includes("اختصاصی")) return "اختصاصی";
  if (n.includes("سهام") || n.includes("شاخص")) return "سهامی";
  if (n.includes("مختلط")) return "مختلط";
  return "سهامی";
}

function premiumPct(f: FundRow): number | null {
  if (f.nav_source !== "nav_record" || !f.nav || !f.price_last) return null;
  return ((f.price_last - f.nav) / f.nav) * 100;
}

function TypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    "سهامی": "bg-accent-emerald/15 text-accent-emerald",
    "درآمد ثابت": "bg-accent-cyan/15 text-accent-cyan",
    "اهرمی": "bg-accent-purple/15 text-accent-purple",
    "مختلط": "bg-accent-amber/15 text-accent-amber",
    "کالایی": "bg-accent-gold/15 text-accent-gold",
  };
  return (
    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold whitespace-nowrap ${map[type] ?? "bg-surface-600/30 text-surface-400"}`}>
      {type}
    </span>
  );
}

// ── Shared shelf state ──────────────────────────────────────────────────────

function useFundShelf() {
  const { data: fundsData, isPending } = useFundList();
  const funds = useMemo(() => fundsData?.items ?? [], [fundsData]);

  const navSymbols = useMemo(() => funds.slice(0, 100).map((f) => f.symbol).join(","), [funds]);
  const { data: navHistory } = useQuery({
    queryKey: ["funds-nav-history", navSymbols],
    queryFn: async () => {
      if (!navSymbols) return {};
      try {
        const res = await apiGet<{ symbols?: Record<string, { date: string; nav: number }[]> }>(
          `/funds/nav-history?symbols=${encodeURIComponent(navSymbols)}&limit=60`
        );
        return res?.symbols ?? {};
      } catch {
        return {};
      }
    },
    staleTime: 120_000,
  });

  const spark = useMemo(() => {
    const out: Record<string, FundNavPoint[]> = {};
    for (const [sym, pts] of Object.entries(navHistory ?? {})) {
      const clean = (pts ?? [])
        .map((p) => ({ date: p.date, nav: Number(p.nav) }))
        .filter((p) => Number.isFinite(p.nav) && p.nav > 0 && p.date);
      if (clean.length > 1) out[sym] = clean.slice(-30);
    }
    return out;
  }, [navHistory]);

  return { funds, isPending, spark };
}

// ── Tab: نمای کلی ───────────────────────────────────────────────────────────

function OverviewTab() {
  const { data: ov, isPending } = useFundOverview();
  if (isPending) return <Loading rows={5} />;
  if (!ov) return <Empty text="نمای کلی بازار ساخته نشد" icon={LayoutDashboard} />;

  const donut = (ov.trade_breakdown ?? []).map((c, i) => ({
    name: c.name,
    value: c.value,
    color: ["#10b981", "#06b6d4", "#f59e0b", "#eab308", "#a78bfa", "#64748b", "#f43f5e"][i % 7],
  }));

  return (
    <div className="space-y-4">
      <Panel title="خلاصه امروز بازار صندوق‌ها" desc={`آخرین به‌روزرسانی ${fmtDate(ov.updated_at)}`}>
        <StatGrid cols={4}>
          <Stat label="صندوق قابل معامله" value={fmt(ov.summary.fund_count)} tone="accent" icon={Landmark} />
          <Stat label="دسته‌بندی" value={fmt(ov.summary.category_count)} icon={Tags} />
          <Stat
            label="میانگین تغییر NAV"
            value={fmtPct(ov.summary.avg_change_pct)}
            tone={ov.summary.avg_change_pct >= 0 ? "pos" : "neg"}
            sub="میانگین بریده (حذف شدوندهای اسنپ‌شات)"
            icon={TrendingUp}
          />
          <Stat label="ارزش کل معاملات" value={fmtBig(ov.summary.total_trade_value)} icon={Banknote} />
        </StatGrid>
        {ov.summary.top_category && (
          <p className="mt-3 text-[11px] text-surface-500">
            داغ‌ترین دسته امروز:{" "}
            <span className="text-accent-amber font-bold">{ov.summary.top_category.name ?? "—"}</span>
          </p>
        )}
      </Panel>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="سهم دسته‌ها از ارزش معاملات" desc="درصد ارزش معاملاتی امروز به تفکیک نوع صندوق">
          {donut.length ? <PieChartCard title="" data={donut} /> : <Empty text="دسته‌ای خالی نیست؟" />}
        </Panel>
        <Panel title="جریان پول حقیقی به تفکیک دسته" desc="خالص خرید minus فروش حقیقی — مثبت یعنی ورود پول">
          <BarChartCard
            title=""
            data={(ov.categories ?? []).map((c) => ({ date: c.name, value: c.real_inflow }))}
            height={240}
            valueLabel="خالص ریالی"
          />
        </Panel>
      </div>

      <Panel title="دسته‌بندی‌ها" desc="میانگین تغییر، ارزش معاملاتی و净流入 هر دسته">
        <DataTable
          rows={ov.categories as unknown as Record<string, unknown>[]}
          columns={[
            { key: "name", label: "دسته", render: (r) => <span className="font-bold text-surface-100">{String(r.name)}</span> },
            { key: "count", label: "تعداد", render: (r) => <span dir="ltr">{fmt(r.count)}</span> },
            {
              key: "avg_change_pct",
              label: "میانگین تغییر",
              render: (r) => <span dir="ltr" className={Number(r.avg_change_pct) >= 0 ? "text-accent-emerald" : "text-accent-rose"}>{fmtPct(Number(r.avg_change_pct))}</span>,
            },
            { key: "trade_value", label: "ارزش معاملاتی", render: (r) => <span dir="ltr">{fmtBig(r.trade_value)}</span> },
            { key: "share_pct", label: "سهم ٪", render: (r) => <span dir="ltr">{fmt(r.share_pct, 1)}٪</span> },
            {
              key: "real_inflow",
              label: "净流入 حقیقی",
              render: (r) => <span dir="ltr" className={Number(r.real_inflow) >= 0 ? "text-accent-emerald" : "text-accent-rose"}>{fmtBig(r.real_inflow)}</span>,
            },
          ]}
        />
      </Panel>

      <Panel title="بازده دوره‌ای دسته‌ها" desc="میانه بازده صندوق‌های هر دسته در بازه‌های یک، سه، شش ماهه و یک ساله">
        {(ov.returns ?? []).length ? (
          <DataTable
            rows={ov.returns as unknown as Record<string, unknown>[]}
            columns={[
              { key: "name", label: "دسته", render: (r) => <span className="font-bold text-surface-100">{String(r.name)}</span> },
              { key: "m1", label: "۱ ماه", render: (r) => <Pct v={r.m1} /> },
              { key: "m3", label: "۳ ماه", render: (r) => <Pct v={r.m3} /> },
              { key: "m6", label: "۶ ماه", render: (r) => <Pct v={r.m6} /> },
              { key: "y1", label: "۱ سال", render: (r) => <Pct v={r.y1} /> },
            ]}
          />
        ) : (
          <Empty text="بازده دوره‌ای محاسبه نشده" hint="برای این محاسبه به تاریخچه قیمت هر صندوق نیاز است." />
        )}
      </Panel>
      <SourceNote>
        <code>/funds/overview</code> — کش سطح‌بندی‌شده با Stale-While-Revalidate؛ ساخت دوباره کش، درخواست را بلاک نمی‌کند.
      </SourceNote>
    </div>
  );
}

function Pct({ v }: { v: unknown }) {
  // Checked before Number(): `Number(null)` is 0, which drew an unmeasured change as a flat
  // ۰٪ — a reading, not an absence.
  if (v === null || v === undefined || v === "") return <span className="text-surface-600">—</span>;
  const n = Number(v);
  if (!Number.isFinite(n)) return <span className="text-surface-600">—</span>;
  return (
    <span dir="ltr" className={n >= 0 ? "text-accent-emerald" : "text-accent-rose"}>
      {fmtPct(n)}
    </span>
  );
}

// ── Tab: قفسه ───────────────────────────────────────────────────────────────

function ShelfTab({
  funds,
  spark,
  loading,
  selected,
  onToggle,
  watch,
  onWatch,
}: {
  funds: FundRow[];
  spark: Record<string, FundNavPoint[]>;
  loading: boolean;
  selected: Set<string>;
  onToggle: (s: string) => void;
  watch: string[];
  onWatch: (s: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [type, setType] = useState("همه");
  const [sort, setSort] = useState("market_value");
  const types = useMemo(() => Array.from(new Set(["همه", ...funds.map((f) => fundType(f.name, f.fund_type))])), [funds]);

  const rows = useMemo(() => {
    let list = funds;
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((f) => f.symbol.toLowerCase().includes(q) || (f.name ?? "").toLowerCase().includes(q) || (f.isin ?? "").toLowerCase().includes(q));
    if (type !== "همه") list = list.filter((f) => fundType(f.name, f.fund_type) === type);
    return [...list].sort((a, b) => {
      switch (sort) {
        case "change":
          return rankNum(b.nav_change_pct) - rankNum(a.nav_change_pct);
        case "volume":
          return rankNum(b.trade_volume) - rankNum(a.trade_volume);
        case "value":
          return rankNum(b.trade_value) - rankNum(a.trade_value);
        case "nav":
          return rankNum(b.nav) - rankNum(a.nav);
        case "premium":
          return (premiumPct(b) ?? -999) - (premiumPct(a) ?? -999);
        default:
          return rankNum(b.market_value) - rankNum(a.market_value);
      }
    });
  }, [funds, search, type, sort]);

  if (loading) return <div className="space-y-2">{[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}</div>;

  return (
    <Panel
      title="قفسه صندوق‌ها"
      desc={`${rows.length} صندوق — برای دیدن میز کار کامل هر نماد کلیک کنید`}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="نام، نماد یا ISIN…"
            className="px-3 py-1.5 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-[11px] focus:outline-none focus:border-primary-500 w-44"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="px-2 py-1.5 bg-surface-800 border border-surface-700 rounded-lg text-surface-300 text-[11px]"
          >
            <option value="market_value">ارزش بازار</option>
            <option value="change">تغییر NAV</option>
            <option value="volume">حجم</option>
            <option value="value">ارزش معاملات</option>
            <option value="nav">NAV</option>
            <option value="premium">صرف/کسر</option>
          </select>
        </div>
      }
    >
      <div className="flex gap-1 flex-wrap mb-3">
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-colors ${
              type === t ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <Empty text="صندوقی با این فیلترها نیست" icon={Filter} />
      ) : (
        <div className="space-y-2">
          {rows.slice(0, 120).map((f) => {
            const p = premiumPct(f);
            const change = f.nav_change_pct;
            const up = change !== null && change >= 0;
            const on = selected.has(f.symbol);
            return (
              <div
                key={f.symbol}
                className={`glass-card p-3 flex items-center gap-3 transition-all group ${on ? "ring-1 ring-primary-500/60" : ""}`}
              >
                <button
                  onClick={() => onToggle(f.symbol)}
                  title={on ? "حذف از مقایسه" : "افزودن به مقایسه"}
                  className={`shrink-0 w-6 h-6 rounded-lg border flex items-center justify-center transition-all ${
                    on ? "bg-primary-600 border-primary-500 text-white" : "border-surface-600 text-transparent hover:border-primary-500"
                  }`}
                >
                  <Check className="w-3 h-3" />
                </button>
                <button
                  onClick={() => onWatch(f.symbol)}
                  title={watch.includes(f.symbol) ? "حذف از علاقه‌مندی‌ها" : "افزودن به علاقه‌مندی‌ها"}
                  className={`shrink-0 w-6 h-6 rounded-lg flex items-center justify-center transition-colors ${
                    watch.includes(f.symbol) ? "text-accent-amber" : "text-surface-600 hover:text-accent-amber"
                  }`}
                >
                  <Star className={`w-3.5 h-3.5 ${watch.includes(f.symbol) ? "fill-current" : ""}`} />
                </button>
                <AddAlertButton compact symbol={f.symbol} market="fund" entry={typeof f.nav === "number" ? f.nav : undefined} />
                <div className="shrink-0 w-[84px] hidden sm:block">
                  {spark[f.symbol]?.length > 1 ? (
                    <FundNavMiniChart points={spark[f.symbol]} width={84} height={28} />
                  ) : (
                    <div className="h-[28px] flex items-center justify-center text-[9px] text-surface-600">—</div>
                  )}
                </div>
                <Link href={`/funds/${encodeURIComponent(f.symbol)}`} className="flex-1 min-w-0 grid grid-cols-2 md:grid-cols-6 gap-2 items-center">
                  <div className="min-w-0">
                    <p className="font-bold text-surface-50 text-sm group-hover:text-primary-300 transition-colors">{f.symbol}</p>
                    <p className="text-[10px] text-surface-500 truncate">{f.name || "—"}</p>
                  </div>
                  <div><TypeBadge type={fundType(f.name, f.fund_type)} /></div>
                  <div className="text-right">
                    <p className="text-[9px] text-surface-600">NAV</p>
                    <p className="font-mono text-xs text-surface-200" dir="ltr">{fmt(f.nav)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[9px] text-surface-600">تغییر</p>
                    <p className={`font-mono text-xs font-bold ${change === null ? "text-surface-600" : toneText(up ? "pos" : "neg")}`} dir="ltr">{fmtPct(change)}</p>
                  </div>
                  <div className="text-right hidden md:block">
                    <p className="text-[9px] text-surface-600">صرف/کسر</p>
                    <p className={`font-mono text-xs ${p === null ? "text-surface-600" : toneText(p >= 0 ? "pos" : "neg")}`} dir="ltr">
                      {p === null ? "—" : fmtPct(p)}
                    </p>
                  </div>
                  <div className="text-right hidden md:block">
                    <p className="text-[9px] text-surface-600">ارزش بازار</p>
                    <p className="font-mono text-xs text-primary-300" dir="ltr">{fmtBig(f.market_value)}</p>
                  </div>
                </Link>
              </div>
            );
          })}
        </div>
      )}
      <SourceNote>
        ستون «صرف/کسر» فقط وقتی عدد می‌گیرد که NAV صدور/ابطال همان نماد ثبت شده باشد؛ در غیر این صورت خالی می‌ماند.
      </SourceNote>
    </Panel>
  );
}

// ── Tab: غربالگر ────────────────────────────────────────────────────────────

interface ScreenerState {
  type: string;
  market: string;
  minChange: number;
  maxChange: number;
  minAum: number;
  minVolume: number;
  premiumMin: number;
  premiumMax: number;
  needNav: boolean;
}

const EMPTY_SCREEN: ScreenerState = {
  type: "همه",
  market: "all",
  minChange: -100,
  maxChange: 100,
  minAum: 0,
  minVolume: 0,
  premiumMin: -10,
  premiumMax: 10,
  needNav: false,
};

function ScreenerTab({ funds, loading, initialType }: { funds: FundRow[]; loading: boolean; initialType?: string }) {
  const [s, setS] = useState<ScreenerState>({ ...EMPTY_SCREEN, type: initialType || EMPTY_SCREEN.type });
  const set = <K extends keyof ScreenerState>(k: K, v: ScreenerState[K]) => setS((p) => ({ ...p, [k]: v }));
  const types = useMemo(() => Array.from(new Set(["همه", ...funds.map((f) => fundType(f.name, f.fund_type))])), [funds]);

  const rows = useMemo(() => {
    if (loading) return [];
    return funds.filter((f) => {
      if (s.type !== "همه" && fundType(f.name, f.fund_type) !== s.type) return false;
      if (s.market !== "all" && f.market !== s.market) return false;
      // A range filter only matches funds whose figure was actually measured — null must not
      // satisfy `null < min` by coercing to zero.
      // A fund whose figure was never measured passes a range the user left wide open and
      // fails one they narrowed. `null < -100` would coerce to 0 and match, which is how an
      // unread value used to be reported as a measurement; hiding it from the default view
      // would be the opposite error.
      const changeNarrowed = s.minChange !== EMPTY_SCREEN.minChange || s.maxChange !== EMPTY_SCREEN.maxChange;
      if (changeNarrowed && (f.nav_change_pct === null || f.nav_change_pct < s.minChange || f.nav_change_pct > s.maxChange)) return false;
      if (s.minAum > EMPTY_SCREEN.minAum && (f.market_value === null || f.market_value < s.minAum)) return false;
      if (s.minVolume > EMPTY_SCREEN.minVolume && (f.trade_volume === null || f.trade_volume < s.minVolume)) return false;
      if (s.needNav && f.nav_source !== "nav_record") return false;
      const p = premiumPct(f);
      if (p === null) return s.premiumMin <= -10 && s.premiumMax >= 10;
      return p >= s.premiumMin && p <= s.premiumMax;
    });
  }, [funds, s, loading]);

  if (loading) return <Loading rows={5} />;

  return (
    <div className="space-y-4">
      <Panel title="غربالگر چندمعیاره" desc="همه شرطها روی همان لحظه بازار اعمال می‌شوند؛ بازه‌ها شامل دو سر هستند.">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <Field label="نوع صندوق">
            <select value={s.type} onChange={(e) => set("type", e.target.value)} className={inputCls}>
              {types.map((t) => <option key={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="بازار">
            <select value={s.market} onChange={(e) => set("market", e.target.value)} className={inputCls}>
              <option value="all">همه</option>
              <option value="tse">بورس تهران</option>
              <option value="ime">بورس کالا</option>
            </select>
          </Field>
          <Field label="فقط صندوق‌های دارای NAV رسمی">
            <button
              onClick={() => set("needNav", !s.needNav)}
              className={`w-full text-[11px] font-bold px-3 py-2 rounded-lg border transition-colors ${
                s.needNav ? "bg-primary-600/20 border-primary-600/40 text-primary-200" : "bg-surface-800 border-surface-700 text-surface-400"
              }`}
            >
              {s.needNav ? "فعال — NAV صدور/ابطال" : "بدون محدودیت"}
            </button>
          </Field>
          <RangeField label="تغییر NAV (٪)" min={-30} max={30} value={[s.minChange, s.maxChange]} onChange={([a, b]) => { set("minChange", a); set("maxChange", b); }} />
          <RangeField label="صرف/کسر (٪)" min={-10} max={10} value={[s.premiumMin, s.premiumMax]} onChange={([a, b]) => { set("premiumMin", a); set("premiumMax", b); }} />
          <Field label={`حداقل ارزش بازار: ${fmtBig(s.minAum) || "بدون کف"}`}>
            <input type="range" min={0} max={5e12} step={1e10} value={s.minAum} onChange={(e) => set("minAum", Number(e.target.value))} className="w-full accent-primary-500" />
          </Field>
          <Field label={`حداقل حجم معامله: ${fmtBig(s.minVolume) || "بدون کف"}`}>
            <input type="range" min={0} max={2e9} step={1e7} value={s.minVolume} onChange={(e) => set("minVolume", Number(e.target.value))} className="w-full accent-primary-500" />
          </Field>
          <Field label=" ">
            <button onClick={() => setS(EMPTY_SCREEN)} className="w-full text-[11px] px-3 py-2 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 transition-colors">
              بازنشانی شرطها
            </button>
          </Field>
        </div>
      </Panel>

      <Panel title="نتیجه غربال" desc={`${rows.length} صندوق مطابق شرطها`}>
        {rows.length ? (
          <DataTable
            rows={rows.slice(0, 200) as unknown as Record<string, unknown>[]}
            columns={[
              {
                key: "symbol",
                label: "نماد",
                render: (r) => (
                  <Link href={`/funds/${encodeURIComponent(String(r.symbol))}`} className="font-bold text-surface-100 hover:text-primary-300 transition-colors">
                    {String(r.symbol)}
                  </Link>
                ),
              },
              { key: "name", label: "نام", render: (r) => <span className="text-surface-400 text-[10px]">{String(r.name ?? "—")}</span> },
              { key: "type", label: "نوع", render: (r) => <TypeBadge type={fundType(String(r.name ?? ""), String(r.fund_type ?? ""))} /> },
              { key: "nav_change_pct", label: "تغییر", render: (r) => <Pct v={r.nav_change_pct} /> },
              {
                key: "premium",
                label: "صرف/کسر",
                render: (r) => {
                  const p = premiumPct(r as unknown as FundRow);
                  return p === null ? <span className="text-surface-600">—</span> : <Pct v={p} />;
                },
              },
              { key: "market_value", label: "ارزش بازار", render: (r) => <span dir="ltr">{fmtBig(r.market_value)}</span> },
              { key: "trade_volume", label: "حجم", render: (r) => <span dir="ltr">{fmtBig(r.trade_volume)}</span> },
              { key: "nav", label: "NAV", render: (r) => <span dir="ltr">{fmt(r.nav)}</span> },
            ]}
            maxHeight={460}
          />
        ) : (
          <Empty text="هیچ صندوقی با این شرطها مطابقت ندارد" hint="بازه‌ها را گشادتر کنید یا دکمه بازنشانی را بزنید." icon={SearchX} />
        )}
      </Panel>
    </div>
  );
}

const inputCls = "w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-[11px] focus:outline-none focus:border-primary-500";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[10px] text-surface-500 mb-1">{label}</span>
      {children}
    </label>
  );
}

function RangeField({
  label,
  min,
  max,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  value: [number, number];
  onChange: (v: [number, number]) => void;
}) {
  return (
    <Field label={`${label} — از ${fmtPct(value[0], 0)} تا ${fmtPct(value[1], 0)}`}>
      <div className="flex items-center gap-2">
        <input type="range" min={min} max={max} value={value[0]} onChange={(e) => onChange([Math.min(Number(e.target.value), value[1]), value[1]])} className="flex-1 accent-primary-500" />
        <input type="range" min={min} max={max} value={value[1]} onChange={(e) => onChange([value[0], Math.max(Number(e.target.value), value[0])])} className="flex-1 accent-primary-500" />
      </div>
    </Field>
  );
}

// ── Tabs: ranking / flows / movers / watchlist / data ───────────────────────

function RankingTab() {
  const { data, isPending } = useFundRankings(100);
  if (isPending) return <Loading rows={6} />;
  const rows = data?.rankings ?? [];
  return (
    <Panel title="رتبه‌بندی کمی صندوق‌ها" desc="آخرین امتیاز هر صندوق با شارپ و حداکثر افت — بر پایه موتور امتیاز v2">
      {rows.length ? (
        <DataTable
          rows={rows as unknown as Record<string, unknown>[]}
          columns={[
            { key: "rank", label: "#", render: (r) => <span className="font-mono text-primary-300" dir="ltr">{Number(r.rank)}</span> },
            {
              key: "symbol",
              label: "صندوق",
              render: (r) => (
                <Link href={`/funds/${encodeURIComponent(String(r.symbol))}`} className="font-bold text-surface-100 hover:text-primary-300 transition-colors">
                  {String(r.symbol)} <span className="text-[10px] text-surface-500 font-normal">{String(r.name ?? "")}</span>
                </Link>
              ),
            },
            { key: "fund_type", label: "نوع", render: (r) => <TypeBadge type={String(r.fund_type ?? "")} /> },
            { key: "total_score", label: "امتیاز", render: (r) => <span dir="ltr" className="font-bold">{fmt(r.total_score, 1)}</span> },
            { key: "sharpe", label: "شارپ", render: (r) => <span dir="ltr">{fmt(r.sharpe, 2)}</span> },
            { key: "max_drawdown", label: "حداکثر افت", render: (r) => <span dir="ltr" className="text-accent-rose">{fmt(r.max_drawdown, 1)}٪</span> },
            { key: "score_date", label: "تاریخ", render: (r) => <span dir="ltr">{fmtDate(r.score_date)}</span> },
          ]}
          maxHeight={520}
        />
      ) : (
        <Empty text="رتبه‌بندی تولید نشده" hint="پس از اولین چرخه امتیازدهی دوره‌ای پر می‌شود." icon={Trophy} />
      )}
      <SourceNote>
        <code>/funds/v2/rankings</code>
      </SourceNote>
    </Panel>
  );
}

function FlowsTab() {
  const { data: ov } = useFundOverview();
  const { data: diffs, isPending } = usePortfolioDiffs();
  const rows = diffs?.diffs ?? [];

  return (
    <div className="space-y-4">
      <Panel title="جریان نقدی دسته‌ها در دوره‌های مختلف" desc="میلیارد تومان خالص ورود/خروج حقیقی — منفی یعنی خروج پول از آن دسته">
        {(ov?.cashflow_periods ?? []).length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="text-right py-2 px-2">دوره</th>
                  {Array.from(new Set((ov?.categories ?? []).map((c) => c.name))).slice(0, 8).map((c) => (
                    <th key={c} className="text-right py-2 px-2 whitespace-nowrap">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(ov?.cashflow_periods ?? []).map((p) => (
                  <tr key={p} className="border-b border-surface-800/60">
                    <td className="py-2 px-2 text-surface-400">{p === "today" ? "امروز" : p === "w1" ? "هفته" : p === "m1" ? "یک ماه" : p === "m3" ? "سه ماه" : p}</td>
                    {Object.entries(ov?.cashflow?.[p] ?? {}).map(([cat, v]) => (
                      <td key={cat} dir="ltr" className={`py-2 px-2 font-mono ${(v as number) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {(v as number).toLocaleString("fa-IR", { maximumFractionDigits: 1 })}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Loading rows={4} />
        )}
      </Panel>

      <Panel title="بزرگ‌ترین تغییرات وزنی بین دو گزارش" desc="دارایی‌هایی که صندوق‌ها بیشترین خرید یا فروش را روی آن‌ها داشته‌اند">
        {isPending ? (
          <Loading rows={4} />
        ) : rows.length ? (
          <DataTable
            rows={rows.slice(0, 60) as unknown as Record<string, unknown>[]}
            columns={[
              {
                key: "fund_symbol",
                label: "صندوق",
                render: (r) => (r.fund_symbol ? <Link href={`/funds/${encodeURIComponent(String(r.fund_symbol))}`} className="font-bold text-surface-100 hover:text-primary-300">{String(r.fund_symbol)}</Link> : "—"),
              },
              { key: "instrument_symbol", label: "دارایی", render: (r) => <span className="text-surface-300">{String(r.instrument_symbol ?? "—")}</span> },
              { key: "period", label: "دوره", render: (r) => <span dir="ltr">{fmtDate(r.period)}</span> },
              { key: "weight_change_pct", label: "تغییر وزن", render: (r) => <Pct v={r.weight_change_pct} /> },
              {
                key: "flow_direction",
                label: "جریان",
                render: (r) => {
                  const map: Record<string, { l: string; t: "pos" | "neg" | "accent" | "muted" }> = {
                    in: { l: "ورود", t: "pos" }, out: { l: "خروج", t: "neg" }, new: { l: "جدید", t: "accent" }, exited: { l: "خروج کامل", t: "neg" },
                  };
                  const m = map[String(r.flow_direction)] ?? { l: String(r.flow_direction ?? "—"), t: "muted" as const };
                  return <Chip label={m.l} tone={m.t} />;
                },
              },
            ]}
            maxHeight={430}
          />
        ) : (
          <Empty text="تغییر وزنی ثبت نشده" hint="دو گزارش ماهانه متوالی از کدال لازم است." />
        )}
      </Panel>
      <SourceNote>
        <code>/funds/overview</code> و <code>/funds/v2/portfolio-diffs</code>
      </SourceNote>
    </div>
  );
}

function MoversTab({ funds, loading }: { funds: FundRow[]; loading: boolean }) {
  if (loading) return <Loading rows={5} />;
  // A mover list is a claim about who moved most, so an unmeasured fund cannot appear in one
  // at all — the old `!== undefined` guard let null through and the sort read it as zero.
  const withChange = funds.filter((f) => f.nav_change_pct !== null);
  const withVolume = funds.filter((f) => f.trade_volume !== null);
  const groups = [
    { title: "بیشترین رشد NAV", rows: [...withChange].sort((a, b) => rankNum(b.nav_change_pct) - rankNum(a.nav_change_pct)).slice(0, 8), icon: TrendingUp, tone: "pos" as const },
    { title: "بیشترین افت NAV", rows: [...withChange].sort((a, b) => rankNum(a.nav_change_pct) - rankNum(b.nav_change_pct)).slice(0, 8), icon: TrendingDown, tone: "neg" as const },
    { title: "پرحجم‌ترین‌ها", rows: [...withVolume].sort((a, b) => rankNum(b.trade_volume) - rankNum(a.trade_volume)).slice(0, 8), icon: BarChart3, tone: "accent" as const },
    { title: "بیشترین صرف", rows: [...withChange].sort((a, b) => (premiumPct(b) ?? -999) - (premiumPct(a) ?? -999)).slice(0, 8), icon: TrendingUp, tone: "warn" as const },
  ];

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {groups.map((g) => (
        <Panel key={g.title} title={g.title} actions={<Chip label={g.title.split(" ")[0] ?? ""} tone={g.tone} icon={g.icon} />}>
          <div className="divide-y divide-surface-800/70">
            {g.rows.map((f) => (
              <Link key={`${g.title}-${f.symbol}`} href={`/funds/${encodeURIComponent(f.symbol)}`} className="flex items-center justify-between gap-2 py-2 hover:bg-white/[0.03] px-2 rounded-lg transition-colors">
                <span className="min-w-0">
                  <span className="font-bold text-surface-100 text-xs">{f.symbol}</span>
                  <span className="block text-[10px] text-surface-500 truncate">{f.name}</span>
                </span>
                <span className={`font-mono text-[11px] font-bold shrink-0 ${toneText(g.tone === "warn" ? (g.title.includes("صرف") ? "warn" : "warn") : g.tone === "pos" ? "pos" : g.tone === "neg" ? "neg" : "accent")}`} dir="ltr">
                  {g.title.includes("صرف") ? (premiumPct(f) === null ? "—" : fmtPct(premiumPct(f)!)) : g.title.includes("حجم") ? fmtBig(f.trade_volume) : fmtPct(f.nav_change_pct)}
                </span>
              </Link>
            ))}
            {!g.rows.length && <Empty text="داده‌ای نیست" />}
          </div>
        </Panel>
      ))}
    </div>
  );
}

function WatchlistTab({ funds, spark, loading, onToggle }: { funds: FundRow[]; spark: Record<string, FundNavPoint[]>; loading: boolean; onToggle: (s: string) => void }) {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    try {
      setIds(JSON.parse(localStorage.getItem(WATCH_KEY) ?? "[]") as string[]);
    } catch {
      setIds([]);
    }
  }, []);
  const rows = funds.filter((f) => ids.includes(f.symbol));

  return (
    <Panel title="علاقه‌مندی‌های من" desc="فقط در همین مرورگر ذخیره می‌شود و به سرور ارسال نمی‌گردد.">
      {loading ? (
        <Loading rows={3} />
      ) : rows.length ? (
        <DataTable
          rows={rows as unknown as Record<string, unknown>[]}
          columns={[
            { key: "symbol", label: "نماد", render: (r) => <Link href={`/funds/${encodeURIComponent(String(r.symbol))}`} className="font-bold text-surface-100 hover:text-primary-300">{String(r.symbol)}</Link> },
            { key: "name", label: "نام", render: (r) => <span className="text-surface-400 text-[10px]">{String(r.name ?? "—")}</span> },
            { key: "nav_change_pct", label: "تغییر", render: (r) => <Pct v={r.nav_change_pct} /> },
            { key: "nav", label: "NAV", render: (r) => <span dir="ltr">{fmt(r.nav)}</span> },
            {
              key: "action",
              label: "",
              render: (r) => (
                <button onClick={() => onToggle(String(r.symbol))} className="text-[10px] px-2 py-1 rounded-lg bg-accent-rose/15 text-accent-rose hover:bg-accent-rose/25 font-bold transition-colors">
                  حذف
                </button>
              ),
            },
          ]}
        />
      ) : (
        <Empty text="هنوز صندوقی به علاقه‌مندی‌ها اضافه نشده" hint="از ستارهٔ کنار هر ردیف در قفسه صندوق‌ها استفاده کنید." icon={Star} />
      )}
      {rows.length > 0 && rows.some((f) => spark[f.symbol]?.length > 1) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          {rows.slice(0, 8).map((f) => (
            <div key={`spark-${f.symbol}`} className="bg-surface-800/40 rounded-lg p-2">
              <p className="text-[10px] text-surface-500 mb-1">{f.symbol}</p>
              {spark[f.symbol]?.length > 1 ? <FundNavMiniChart points={spark[f.symbol]} width={140} height={32} /> : <p className="text-[9px] text-surface-600">تاریخچه NAV نیست</p>}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function DataTab() {
  const { data: m, isPending } = useFundMonitoring();
  const { data: cov } = useFundCoverage();
  const d = (m ?? {}) as Record<string, unknown>;
  return (
    <div className="space-y-4">
      <Panel title="پایش ماژول صندوق‌ها" desc="شمارشگرهای پایگاه داده — میزبان سلامت داده پیش از تحلیل">
        {isPending ? (
          <Loading rows={2} />
        ) : (
          <StatGrid cols={3}>
            <Stat label="Universe صندوق‌ها" value={fmt(d.universe_count)} tone="accent" />
            <Stat label="رکورد تاریخچه NAV" value={fmt(d.nav_history_rows)} />
            <Stat label="رکورد ترکیب دارایی" value={fmt(d.holdings_rows)} />
            <Stat label="امتیاز دوره‌ای" value={fmt(d.scores_rows)} />
            <Stat label="قرنطینه بازبینی‌نشده" value={fmt(d.quarantine_unreviewed)} tone={Number(d.quarantine_unreviewed) ? "neg" : "pos"} />
            <Stat label="قیمت کهنه (بیش از ۵ دقیقه)" value={fmt(d.stale_quotes)} tone={Number(d.stale_quotes) ? "warn" : "pos"} />
          </StatGrid>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          {Object.entries(cov?.summary ?? {}).map(([k, v]) => (
            <MiniMetric key={k} label={`پوشش ${k}`} value={(v as number).toLocaleString("fa-IR")} />
          ))}
        </div>
      </Panel>
      <Panel title="عملیات داده" desc="کشف Universe و همگام‌سازی اسنپ‌شات — روی همه صندوق‌ها، نه فقط این نماد">
        <ActionGroup group="market" />
      </Panel>
      <SourceNote>
        <code>/funds/v2/monitoring</code> و <code>/funds/v2/coverage</code> — جزئیات هر نماد در تب «داده و حسابرسی» میز کار همان صندوق است.
      </SourceNote>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

function FundsPageContent() {
  const { funds, isPending, spark } = useFundShelf();
  const searchParams = useSearchParams();
  const { active, tab, select: onTabChange } = useTabController(GROUPS, "overview");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);
  const [watch, setWatch] = useState<string[]>([]);

  // Deep link from the homepage map tiles (?type=…) opens the screener with that filter
  useEffect(() => {
    if (searchParams?.get("type")) onTabChange("screener");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire on URL change only
  }, [searchParams]);

  useEffect(() => {
    try {
      setWatch(JSON.parse(localStorage.getItem(WATCH_KEY) ?? "[]") as string[]);
    } catch {
      setWatch([]);
    }
  }, []);

  function toggleWatch(symbol: string) {
    setWatch((prev) => {
      const next = prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol];
      try {
        localStorage.setItem(WATCH_KEY, JSON.stringify(next));
      } catch {
        /* private mode — the list simply will not persist */
      }
      return next;
    });
  }

  function toggleSelect(symbol: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      if (next.size < 2) setCompareOpen(false);
      return next;
    });
  }

  const selectedFunds = useMemo(() => funds.filter((f) => selected.has(f.symbol)), [funds, selected]);
  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const f of funds) map[fundType(f.name, f.fund_type)] = (map[fundType(f.name, f.fund_type)] ?? 0) + 1;
    return map;
  }, [funds]);

  return (
    <AppLayout
      title="🏦 صندوق‌های سرمایه‌گذاری"
      subtitle="بورس تهران و بورس کالا — داده واقعی، بدون داده ساختگی"
      header={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <FundDiscoveryBanner />
          <div className="flex items-center gap-2">
            <FundMarketSyncButton />
          </div>
        </div>
      }
    >
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {Object.entries(counts).slice(0, 6).map(([k, v]) => (
          <Chip key={k} label={`${k}: ${v.toLocaleString("fa-IR")}`} tone="muted" />
        ))}
        <span className="text-[10px] text-surface-600 mr-auto">کل universe: {funds.length.toLocaleString("fa-IR")} صندوق</span>
      </div>

      <TabStrip tabs={TABS} active={active} onSelect={onTabChange} ariaLabel="تب‌های صفحه صندوق‌ها" className="border-b border-surface-700/60 pb-2 mb-4" />

      <TabPanel tab={tab}>
        {active === "overview" && <OverviewTab />}
        {active === "shelf" && <ShelfTab funds={funds} spark={spark} loading={isPending} selected={selected} onToggle={toggleSelect} watch={watch} onWatch={toggleWatch} />}
        {active === "screener" && <ScreenerTab funds={funds} loading={isPending} initialType={searchParams?.get("type") ?? undefined} />}
        {active === "ranking" && <RankingTab />}
        {active === "flows" && <FlowsTab />}
        {active === "movers" && <MoversTab funds={funds} loading={isPending} />}
        {active === "watchlist" && <WatchlistTab funds={funds} spark={spark} loading={isPending} onToggle={toggleWatch} />}
        {active === "data" && <DataTab />}
      </TabPanel>

      {/* star toggle inside the shelf rows */}
      {active === "shelf" && funds.length > 0 && (
        <div className="mt-3 text-[10px] text-surface-600">
          {watch.length > 0 ? `${watch.length.toLocaleString("fa-IR")} صندوق در علاقه‌مندی‌ها — تب «علاقه‌مندی‌ها» را ببینید.` : "برای ذخیره صندوق‌ها در علاقه‌مندی‌ها از تب «علاقه‌مندی‌ها» استفاده کنید."}
        </div>
      )}

      {compareOpen && selectedFunds.length >= 2 && (
        <FundCompareModal funds={selectedFunds as never} onClose={() => setCompareOpen(false)} onRemove={(s) => toggleSelect(s)} />
      )}
      {selected.size >= 2 && active === "shelf" && (
        <button
          onClick={() => setCompareOpen(true)}
          className="fixed bottom-6 left-6 z-40 px-4 py-2.5 rounded-2xl bg-primary-600 hover:bg-primary-500 text-white text-xs font-black shadow-2xl shadow-primary-600/30 transition-all"
        >
          مقایسه {selected.size.toLocaleString("fa-IR")} صندوق
        </button>
      )}
    </AppLayout>
  );
}

export default function FundsPage() {
  return (
    <Suspense fallback={<AppLayout title="صندوق‌های سرمایه‌گذاری"><Skeleton className="h-64 w-full rounded-2xl" /></AppLayout>}>
      <FundsPageContent />
    </Suspense>
  );
}
