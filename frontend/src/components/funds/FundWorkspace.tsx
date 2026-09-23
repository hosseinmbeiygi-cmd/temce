"use client";

/**
 * FundWorkspace — the tabbed funds desk for a single symbol.
 *
 * Eight groups / thirty-four tabs, each bound to a real endpoint under
 * /funds, /funds/v2/{nav,ledger,compliance,regulator}. The active tab lives in
 * `?tab=`, so any panel is shareable and browser back/forward keeps working.
 */

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { TabPanel, TabStrip, useTabController, type TabDef, type TabGroup } from "@/components/ui/Tabs";
import type { FundChecklistSymbolDetailLike } from "@/lib/fund-checklist-real";
import { useFundCoverage, useFundDetail, useFundQuery, useFundV2Score, useFundV2Valuation, useNavDashboard, runFundUpdate } from "@/lib/fund-queries";
import { premiumOf } from "@/components/funds/FundMarketTabs";
import {
  AccessLogTab,
  AuditPackTab,
  AliasesTab,
  AmlTab,
  ComplianceTab,
  CoverageTab,
  CsdiTab,
  EntriesTab,
  GovernanceDocsTab,
  GovernanceTab,
  MonitoringTab,
  QuarantineTab,
  TaxTab,
  TrialBalanceTab,
  UnitMovementsTab,
} from "@/components/funds/FundOpsTabs";
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowLeftRight,
  BadgeCheck,
  Banknote,
  BarChart3,
  BookOpen,
  Building2,
  Calculator,
  CandlestickChart,
  ClipboardCheck,
  ClipboardList,
  Cpu,
  Database,
  FileText,
  Gauge,
  Gavel,
  GitBranch,
  HeartPulse,
  History,
  Landmark,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  LineChart,
  List,
  Network,
  Percent,
  PieChart,
  Receipt,
  Scale,
  ScrollText,
  Search,
  ShieldAlert,
  ShieldCheck,
  Tag,
  TrendingUp,
  Trophy,
  Users,
  Wallet,
  Wand2,
} from "lucide-react";
import {
  ClassNavTab,
  FofTab,
  NavEngineTab,
  NavEvidenceTab,
  NavLayersTab,
  ReconciliationTab,
  ValuationTab,
} from "@/components/funds/FundNavTabs";
import { ActionGroup } from "@/components/funds/FundForms";
import { BacktestTab, CandlesTab, CompositionTab, DiffsTab, HoldingsTab, PeersTab, QuoteTab, RankingsTab, ScoreTab, TicksTab } from "@/components/funds/FundMarketTabs";
import { Chip, Empty, fmt, fmtBig, fmtPct, Loading, MeterBar, MiniMetric, Panel, SourceNote, Stat, StatGrid, toneText } from "@/components/funds/ui";

const FundChecklistPanel = dynamic(() => import("@/components/FundChecklistPanel"), {
  ssr: false,
  loading: () => <Loading rows={4} />,
});

const REC_LABELS: Record<string, string> = {
  STRONG_BUY: "خرید قوی",
  BUY: "خرید",
  WATCHLIST: "تحت نظر",
  HOLD: "نگهداری",
  REDUCE: "کاهش",
  SELL: "فروش",
  AVOID: "اجتناب",
};

const RISK_LABELS: Record<string, string> = { LOW: "کم", MEDIUM: "متوسط", HIGH: "زیاد", CRITICAL: "بحرانی" };
const DIM_LABELS: Record<string, string> = {
  financial: "مالی",
  liquidity: "نقدشوندگی",
  management: "مدیریت",
  risk: "ریسک",
  cost: "هزینه",
  transparency: "شفافیت",
};

// ── Tab catalogue ───────────────────────────────────────────────────────────

const GROUPS: TabGroup[] = [
  {
    id: "general",
    label: "نمای کلی",
    icon: LayoutDashboard,
    tabs: [
      { id: "summary", label: "کارت تصمیم", icon: Wand2 },
      { id: "checklist", label: "چک‌لیست انتخاب", icon: ClipboardCheck },
    ],
  },
  {
    id: "nav",
    label: "NAV و ارزش‌گذاری",
    icon: Calculator,
    tabs: [
      { id: "valuation", label: "ارزش‌گذاری لحظه‌ای", icon: Gauge },
      { id: "nav-layers", label: "سه لایه NAV", icon: Layers },
      { id: "nav-engine", label: "موتور NAV مستقل", icon: Cpu },
      { id: "reconciliation", label: "تطبیق و مغایرت", icon: ShieldCheck },
      { id: "class-nav", label: "NAV طبقاتی", icon: Network },
      { id: "fof", label: "فراصندوق", icon: Network },
      { id: "nav-evidence", label: "مدارک و اجرای سایه", icon: BadgeCheck },
    ],
  },
  {
    id: "market",
    label: "بازار",
    icon: CandlestickChart,
    tabs: [
      { id: "quote", label: "تابلو و جریان پول", icon: Tag },
      { id: "ticks", label: "ریز معاملات", icon: Activity },
      { id: "candles", label: "کندل درون‌روز", icon: LineChart },
    ],
  },
  {
    id: "portfolio",
    label: "سبد دارایی",
    icon: Wallet,
    tabs: [
      { id: "holdings", label: "ریز دارایی", icon: List },
      { id: "composition", label: "ترکیب و تمرکز", icon: PieChart },
      { id: "diffs", label: "تغییرات دوره", icon: ArrowLeftRight },
    ],
  },
  {
    id: "performance",
    label: "عملکرد",
    icon: TrendingUp,
    tabs: [
      { id: "score", label: "امتیاز و ریسک", icon: Gauge },
      { id: "rankings", label: "رتبه‌بندی بازار", icon: Trophy },
      { id: "peers", label: "هم‌گروه‌ها", icon: Users },
      { id: "backtest", label: "بک‌تست", icon: History },
    ],
  },
  {
    id: "ledger",
    label: "دفتر مالی",
    icon: BookOpen,
    tabs: [
      { id: "trial-balance", label: "تراز آزمایشی", icon: Scale },
      { id: "entries", label: "اسناد دوطرفه", icon: Receipt },
      { id: "unit-movements", label: "حرکت واحدها", icon: ArrowLeftRight },
    ],
  },
  {
    id: "compliance",
    label: "انطباق و حاکمیت",
    icon: Gavel,
    tabs: [
      { id: "compliance", label: "وضعیت انطباق", icon: ShieldCheck },
      { id: "aml", label: "AML و STR", icon: AlertTriangle },
      { id: "governance", label: "حاکمیت و حسابرسی", icon: Building2 },
      { id: "tax", label: "مالیات", icon: Percent },
      { id: "docs", label: "اساسنامه، شرعی، شکایت", icon: FileText },
      { id: "csdi", label: "تطبیق با سامانه ثبت", icon: ShieldCheck },
    ],
  },
  {
    id: "data",
    label: "داده و حسابرسی",
    icon: Database,
    tabs: [
      { id: "coverage", label: "پوشش و تازگی", icon: LayoutGrid },
      { id: "quarantine", label: "قرنطینه داده", icon: ShieldAlert },
      { id: "aliases", label: "تغییر نماد", icon: GitBranch },
      { id: "monitoring", label: "پایش ماژول", icon: HeartPulse },
      { id: "audit-pack", label: "بسته مدارک", icon: Archive },
      { id: "access-logs", label: "سابقه دسترسی", icon: History },
    ],
  },
  {
    id: "ops",
    label: "عملیات و ثبت",
    icon: ClipboardList,
    tabs: [
      { id: "ops-nav", label: "محاسبات NAV", icon: Calculator },
      { id: "ops-ledger", label: "دفتر و واحدها", icon: Receipt },
      { id: "ops-compliance", label: "انطباق و اسناد", icon: ScrollText },
      { id: "ops-aml", label: "AML و STR", icon: AlertTriangle },
      { id: "ops-tax", label: "مالیات", icon: Percent },
      { id: "ops-governance", label: "حاکمیت و بیمه", icon: Building2 },
      { id: "ops-csdi", label: "تطبیق CSDI", icon: ShieldCheck },
    ],
  },
];

// ── Decision card ───────────────────────────────────────────────────────────

function SummaryTab({ symbol }: { symbol: string }) {
  const { data: f, isPending } = useFundDetail(symbol);
  const { data: valuation } = useFundV2Valuation(symbol);
  const { data: score } = useFundV2Score(symbol);
  const { data: nav } = useNavDashboard(symbol);
  const { data: coverage } = useFundCoverage();

  const mine = useMemo(
    () => (coverage?.items ?? []).find((r) => String(r.symbol ?? "").toUpperCase() === symbol.toUpperCase()),
    [coverage, symbol]
  );

  if (isPending) return <Loading rows={4} />;
  if (!f || f.found === false) return <Empty text="صندوقی با این نماد پیدا نشد" hint="نماد را از فهرست صندوق‌ها انتخاب کنید." icon={Search} />;

  const a = f.analysis;
  const premium = premiumOf(f);
  const openBreaks = nav?.open_breaks?.length ?? 0;
  const verdict = a ? { label: REC_LABELS[a.recommendation] ?? a.recommendation, tone: toneOf(a.recommendation) } : null;

  return (
    <div className="space-y-4">
      <Panel
        title="کارت تصمیم"
        desc="خلاصه داوری سیستم روی این نماد: نتیجه تحلیل شش‌بعدی، کیفیت داده و مغایرت‌های باز."
        actions={
          <div className="flex items-center gap-2">
            {verdict && <Chip label={verdict.label} tone={verdict.tone} icon={Gavel} />}
            {a && <Chip label={`ریسک ${RISK_LABELS[a.risk_level] ?? a.risk_level}`} tone={riskTone(a.risk_level)} />}
          </div>
        }
      >
        <StatGrid cols={4}>
          <Stat
            label="NAV"
            value={fmt(f.nav)}
            tone="accent"
            sub={f.nav_source === "nav_record" ? `واقعی — ${f.nav_date ?? ""}` : "تقریبی از آخرین قیمت"}
            icon={Landmark}
          />
          <Stat label="قیمت آخرین" value={fmt(f.price_last)} sub={f.time ? `ساعت ${f.time}` : undefined} icon={Tag} />
          <Stat
            label="صرف / کسر"
            value={premium === null ? "—" : fmtPct(premium)}
            tone={premium === null ? "muted" : premium >= 0 ? "pos" : "neg"}
            sub={premium === null ? "به دلیل نبود NAV رسمی" : "قیمت نسبت به NAV صدور"}
            icon={ArrowLeftRight}
          />
          <Stat
            label="پوشش ارزش‌گذاری"
            value={valuation?.coverage_pct != null ? `${fmt(valuation.coverage_pct, 1)}٪` : "—"}
            tone={Number(valuation?.coverage_pct ?? 0) >= 80 ? "pos" : "warn"}
            sub={`امتیاز کمی ${score?.total != null ? score.total.toFixed(0) : "—"}`}
            icon={LayoutGrid}
          />
        </StatGrid>

        {a && (
          <div className="mt-5">
            <p className="text-[11px] text-surface-400 mb-2">اجزای تحلیل شش‌بعدی</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(a.scores ?? {}).map(([k, v]) => (
                <MeterBar key={k} label={DIM_LABELS[k] ?? k} value={Number(v) || 0} />
              ))}
            </div>
            <p className="text-[11px] text-surface-500 mt-3 leading-relaxed">{a.summary}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2 mt-4">
          <Chip label={`${fmt(f.trade_count)} معامله`} tone="muted" icon={Banknote} />
          <Chip label={`حجم ${fmtBig(f.trade_volume)}`} tone="muted" icon={BarChart3} />
          <Chip label={`ارزش بازار ${fmtBig(f.market_value)}`} tone="muted" icon={Wallet} />
          {openBreaks > 0 && <Chip label={`${openBreaks} مغایرت NAV باز`} tone="neg" icon={AlertTriangle} />}
          {a && a.issues_count > 0 && <Chip label={`${a.issues_count} نکته تحلیل`} tone="warn" icon={ClipboardCheck} />}
        </div>
        <SourceNote>
          <code>/funds/{symbol}</code> + <code>/funds/v2/…/valuation</code> + <code>/funds/v2/…/nav/dashboard</code> — اگر
          NAV رسمی امروز منتشر نشده باشد، صرف/کسر عمداً خالی می‌ماند تا عدد گمراه‌کننده نسازد.
        </SourceNote>
      </Panel>

      {mine && (
        <Panel title="وضعیت داده همین نماد" desc="خروجی KPI پوشش — مشخص می‌کند اعداد بالا روی چه پایه‌ای ایستاده‌اند.">
          <KeyValueish row={mine as Record<string, unknown>} />
        </Panel>
      )}
    </div>
  );
}

function KeyValueish({ row }: { row: Record<string, unknown> }) {
  const entries = Object.entries(row).filter(([, v]) => typeof v !== "object");
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {entries.map(([k, v]) => (
        <MiniMetric key={k} label={k} value={typeof v === "number" ? fmt(v, 2) : String(v ?? "—")} />
      ))}
    </div>
  );
}

/** The checklist reads the fund snapshot plus the broker-side symbol detail. */
function ChecklistTab({ symbol }: { symbol: string }) {
  const { data: f, isPending } = useFundDetail(symbol);
  const { data: symbolDetail } = useFundQuery<FundChecklistSymbolDetailLike>(
    ["brsapi", "symbol-details", symbol],
    `/brsapi/symbol-details/${encodeURIComponent(symbol)}`,
    { staleTime: 300_000 }
  );

  if (isPending) return <Loading rows={4} />;
  if (!f || f.found === false) return <Empty text="برای این نماد داده‌ای نیست" />;
  return <FundChecklistPanel fund={f} symbolDetail={symbolDetail ?? undefined} />;
}

function toneOf(rec: string): "pos" | "warn" | "neg" | "muted" {
  if (rec === "STRONG_BUY" || rec === "BUY") return "pos";
  if (rec === "SELL" || rec === "AVOID" || rec === "REDUCE") return "neg";
  if (rec === "WATCHLIST") return "warn";
  return "muted";
}

function riskTone(risk: string): "pos" | "warn" | "neg" {
  return risk === "LOW" ? "pos" : risk === "MEDIUM" ? "warn" : "neg";
}

// ── Tab body router ─────────────────────────────────────────────────────────

function TabBody({ id, symbol }: { id: string; symbol: string }) {
  switch (id) {
    case "summary":
      return <SummaryTab symbol={symbol} />;
    case "checklist":
      return <ChecklistTab symbol={symbol} />;
    case "valuation":
      return <ValuationTab symbol={symbol} />;
    case "nav-layers":
      return <NavLayersTab symbol={symbol} />;
    case "nav-engine":
      return <NavEngineTab symbol={symbol} />;
    case "reconciliation":
      return <ReconciliationTab symbol={symbol} />;
    case "class-nav":
      return <ClassNavTab symbol={symbol} />;
    case "fof":
      return <FofTab symbol={symbol} />;
    case "nav-evidence":
      return <NavEvidenceTab symbol={symbol} />;
    case "quote":
      return <QuoteTab symbol={symbol} />;
    case "ticks":
      return <TicksTab symbol={symbol} />;
    case "candles":
      return <CandlesTab symbol={symbol} />;
    case "holdings":
      return <HoldingsTab symbol={symbol} />;
    case "composition":
      return <CompositionTab symbol={symbol} />;
    case "diffs":
      return <DiffsTab symbol={symbol} />;
    case "score":
      return <ScoreTab symbol={symbol} />;
    case "rankings":
      return <RankingsTab symbol={symbol} />;
    case "peers":
      return <PeersTab symbol={symbol} />;
    case "backtest":
      return <BacktestTab symbol={symbol} />;
    case "trial-balance":
      return <TrialBalanceTab symbol={symbol} />;
    case "entries":
      return <EntriesTab symbol={symbol} />;
    case "unit-movements":
      return <UnitMovementsTab symbol={symbol} />;
    case "compliance":
      return <ComplianceTab symbol={symbol} />;
    case "aml":
      return <AmlTab symbol={symbol} />;
    case "governance":
      return <GovernanceTab symbol={symbol} />;
    case "tax":
      return <TaxTab symbol={symbol} />;
    case "docs":
      return <GovernanceDocsTab symbol={symbol} />;
    case "csdi":
      return <CsdiTab symbol={symbol} />;
    case "coverage":
      return <CoverageTab symbol={symbol} />;
    case "quarantine":
      return <QuarantineTab symbol={symbol} />;
    case "aliases":
      return <AliasesTab symbol={symbol} />;
    case "monitoring":
      return <MonitoringTab />;
    case "audit-pack":
      return <AuditPackTab symbol={symbol} />;
    case "access-logs":
      return <AccessLogTab />;
    case "ops-nav":
      return <ActionGroup group="nav" symbol={symbol} />;
    case "ops-ledger":
      return <ActionGroup group="ledger" symbol={symbol} />;
    case "ops-compliance":
      return <ActionGroup group="compliance" symbol={symbol} />;
    case "ops-aml":
      return <ActionGroup group="aml" symbol={symbol} />;
    case "ops-tax":
      return <ActionGroup group="tax" symbol={symbol} />;
    case "ops-governance":
      return <ActionGroup group="governance" symbol={symbol} />;
    case "ops-csdi":
      return <ActionGroup group="csdi" symbol={symbol} />;
    default:
      return <Empty text="تب ناشناخته" />;
  }
}

// ── Workspace ───────────────────────────────────────────────────────────────

export default function FundWorkspace({ symbol }: { symbol: string }) {
  const qc = useQueryClient();
  const { group, tab, select: onTabChange } = useTabController(GROUPS, "summary");
  const { data: f } = useFundDetail(symbol);
  const [refreshing, setRefreshing] = useState(false);

  const activeGroup = useMemo(() => group, [group]);

  async function refresh() {
    setRefreshing(true);
    try {
      const res = await runFundUpdate(symbol);
      if (res?.error) toast.error(res.error);
      else {
        toast.success("داده‌های صندوق از BrsApi تازه شد");
        qc.invalidateQueries({ queryKey: ["funds"] });
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "به‌روزرسانی ناموفق");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div>
      {/* ── Hero ── */}
      <div className="glass-card p-4 mb-4 relative overflow-hidden">
        <div className="absolute inset-y-0 left-0 w-40 bg-gradient-to-l from-primary-600/10 to-transparent pointer-events-none" aria-hidden />
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-2xl font-black text-surface-50 tracking-tight">{f?.name || symbol}</h2>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-lg bg-primary-600/20 text-primary-200" dir="ltr">
                {symbol}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap mt-2">
              {f?.fund_type && <Chip label={f.fund_type} tone="accent" />}
              <Chip label={f?.market === "ime" ? "بورس کالا" : "بورس تهران"} tone="muted" icon={Landmark} />
              {f?.isin && (
                <span className="text-[10px] font-mono text-surface-500" dir="ltr">
                  ISIN {f.isin}
                </span>
              )}
              {f?.nav_date && (
                <span className="text-[10px] text-surface-500">
                  NAV <span dir="ltr">{f.nav_date}</span>
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0 sm:flex-col sm:items-end">
            <div className="text-left hidden sm:block">
              <p className="text-[10px] text-surface-500">قیمت آخرین</p>
              <p className="font-mono text-lg font-black text-surface-100" dir="ltr">
                {fmt(f?.price_last)}
              </p>
              {f && (
                <p className={`font-mono text-xs font-bold ${f.nav_change_pct === null ? "text-surface-600" : toneText(f.nav_change_pct >= 0 ? "pos" : "neg")}`} dir="ltr">
                  {fmtPct(f.nav_change_pct)}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Link
                href="/funds"
                className="text-[11px] px-3 py-1.5 rounded-lg bg-surface-800 border border-surface-700 text-surface-300 hover:text-surface-100 transition-colors text-center"
              >
                فهرست صندوق‌ها
              </Link>
              <button
                onClick={() => void refresh()}
                disabled={refreshing}
                className="text-[11px] font-bold px-3 py-1.5 rounded-lg bg-primary-600/15 hover:bg-primary-600/25 border border-primary-600/30 text-primary-200 transition-colors disabled:opacity-50"
              >
                {refreshing ? "در حال تازه‌سازی…" : "تازه‌سازی داده"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Group nav ── */}
      <div className="sticky top-0 z-30 -mx-1 px-1 pt-1 pb-2 bg-surface-900/85 backdrop-blur-md">
        <TabStrip
          variant="strip"
          ariaLabel="گروه‌های اطلاعات صندوق"
          tabs={GROUPS.map<TabDef>((g) => ({ id: g.id, label: g.label, icon: g.icon }))}
          active={activeGroup.id}
          onSelect={(gid) => {
            const firstEnabled = GROUPS.find((g) => g.id === gid)?.tabs[0];
            if (firstEnabled) onTabChange(firstEnabled.id);
          }}
          className="flex-wrap border-b border-surface-700/60 pb-2"
        />
        <TabStrip
          variant="strip"
          ariaLabel={`تب‌های گروه ${activeGroup.label}`}
          tabs={activeGroup.tabs}
          active={tab.id}
          onSelect={onTabChange}
          className="flex-wrap pt-2"
        />
      </div>

      <div className="mt-4">
        <TabPanel tab={tab}>
          <TabBody id={tab.id} symbol={symbol} />
        </TabPanel>
      </div>
    </div>
  );
}

export function FundWorkspaceFallback() {
  return (
    <div className="space-y-3">
      <Skeletonish className="h-24 w-full rounded-2xl" />
      <Skeletonish className="h-10 w-full rounded-xl" />
      <Skeletonish className="h-64 w-full rounded-2xl" />
    </div>
  );
}

function Skeletonish({ className }: { className: string }) {
  return <div className={`bg-surface-800/40 animate-pulse ${className}`} />;
}

export function SuspensefulWorkspace({ symbol }: { symbol: string }) {
  return (
    <Suspense fallback={<FundWorkspaceFallback />}>
      <FundWorkspace symbol={symbol} />
    </Suspense>
  );
}
