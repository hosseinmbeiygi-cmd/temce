"use client";

/**
 * Tabs of the "NAV و ارزش‌گذاری" group — the three NAV layers, the independent
 * NAV engine, reconciliation, tiered allocation, fund-of-funds and the audit
 * evidence package (§2 / §7 of the design doc).
 */

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  useClassNav,
  useFundFof,
  useFundV2NavHistory,
  useFundV2Valuation,
  useNavDashboard,
  useNavEvidence,
  useShadowAcceptance,
  runNavCalculation,
  runNavReconciliation,
} from "@/lib/fund-queries";
import { Chip, DataTable, Empty, fmt, fmtBig, fmtDate, fmtPct, KeyValue, Loading, MiniMetric, Panel, SourceNote, Stat, StatGrid } from "@/components/funds/ui";
import { Calculator, Cpu, LineChart, Network } from "lucide-react";
import {
  BREAK_LIFECYCLE_LABELS,
  COMPARABILITY_LABELS,
  DIFF_LABELS,
  QUALITY_LABELS,
  REFERENCE_LABELS,
  labelOf,
  qualityTone,
  diffTone,
  referenceTone,
  formatBps,
} from "@/lib/fund-nav";
import { circularTone, hasCircularExposure } from "@/lib/fund-compliance";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});

function RunButton({ kind, symbol }: { kind: "calculate" | "reconcile"; symbol: string }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const label = kind === "calculate" ? "اجرای محاسبه NAV" : "اجرای تطبیق";
  return (
    <button
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await (kind === "calculate" ? runNavCalculation(symbol) : runNavReconciliation(symbol));
          toast.success(kind === "calculate" ? "محاسبه NAV انجام شد" : "تطبیق انجام شد");
          qc.invalidateQueries({ queryKey: ["funds", "nav"] });
        } catch (e) {
          toast.error(e instanceof Error ? e.message : "اخراج خطا");
        } finally {
          setBusy(false);
        }
      }}
      className="text-[11px] font-bold px-3 py-1.5 rounded-lg bg-primary-600/15 hover:bg-primary-600/25 border border-primary-600/30 text-primary-200 transition-colors disabled:opacity-50"
    >
      {busy ? "در حال اجرا…" : label}
    </button>
  );
}

// ── ۱. ارزش‌گذاری لحظه‌ای ───────────────────────────────────────────────────

export function ValuationTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundV2Valuation(symbol);
  const divergence = useMemo(() => {
    const est = Number(data?.nav_estimated);
    const off = Number(data?.nav_official);
    if (!Number.isFinite(est) || !Number.isFinite(off) || !off) return null;
    return ((est - off) / off) * 100;
  }, [data]);

  if (isPending) return <Loading rows={4} />;
  if (!data) return <Empty text="ارزش‌گذاری بازنگشت" icon={Calculator} />;

  return (
    <Panel title="ارزش‌گذاری لحظه‌ای" desc="NAV تخمینی از ریز دارایی‌ها به‌همراه درصد پوشش دارایی‌هایی که قیمت زنده دارند.">
      <StatGrid cols={4}>
        <Stat label="NAV تخمینی" value={fmt(data.nav_estimated, 2)} tone="accent" sub="از ترکیب دارایی + قیمت لحظه‌ای" />
        <Stat label="NAV رسمی" value={fmt(data.nav_official, 2)} sub="ناشر / کدال" />
        <Stat
          label="انحراف تخمین از رسمی"
          value={divergence === null ? "—" : fmtPct(divergence)}
          tone={divergence === null ? "default" : Math.abs(divergence) < 1 ? "pos" : Math.abs(divergence) < 3 ? "warn" : "neg"}
        />
        <Stat label="پوشش دارایی‌ها" value={`${fmt(data.coverage_pct, 1)}٪`} tone={Number(data.coverage_pct) >= 80 ? "pos" : "warn"} />
      </StatGrid>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
        <MiniMetric label="ارزش سهام" value={fmtBig(data.equity_value)} />
        <MiniMetric label="نقد و درآمد ثابت" value={fmtBig(data.cash_and_fixed_income)} />
        <MiniMetric label="ارزش کل دارایی" value={fmtBig(data.total_value)} />
        <MiniMetric label="واحدهای در گردش" value={fmtBig(data.units_outstanding)} />
      </div>
      <SourceNote>
        <code>/funds/v2/{symbol}/valuation</code> — موتور Read-Through با Gap-Filling؛ در نبود داده جدید،
        از کش با برچسب تازگی استفاده می‌شود.
      </SourceNote>
    </Panel>
  );
}

// ── ۲. سه لایه NAV ──────────────────────────────────────────────────────────

export function NavLayersTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundV2NavHistory(symbol);
  const points = useMemo(() => data?.points ?? [], [data]);

  const series = useMemo(
    () =>
      points.map((p) => ({
        date: p.date,
        stat: Number(p.nav_statistical ?? p.nav_redemption ?? p.nav_issue ?? 0),
        issue: Number(p.nav_issue ?? 0),
        redeem: Number(p.nav_redemption ?? 0),
      })),
    [points]
  );

  if (isPending) return <Loading rows={5} />;
  if (!points.length)
    return <Empty text="تاریخچه NAV سه‌لایه موجود نیست" hint="پس از اولین همگام‌سازی صدور/ابطال، این نمودار پر می‌شود." icon={LineChart} />;

  const latest = points[points.length - 1];

  return (
    <div className="space-y-4">
      <Panel title="سه لایه NAV" desc="صدور، ابطال و قیمت آماری در کنار هم — اختلاف این سه، اولین نشانه فشار نقدینگی یا صف است.">
        <div className="grid grid-cols-3 gap-3 mb-4">
          <MiniMetric label={`آخرین صدور (${fmtDate(latest?.date)})`} value={fmt(latest?.nav_issue, 2)} />
          <MiniMetric label="آخرین ابطال" value={fmt(latest?.nav_redemption, 2)} />
          <MiniMetric label="آخرین قیمت آماری" value={fmt(latest?.nav_statistical, 2)} tone="accent" />
        </div>
        <AreaChartCard
          title="روند NAV آماری"
          data={series.map((s) => ({ date: s.date, value: s.stat }))}
          dataKey="value"
          height={250}
          strokeColor="#10b981"
          gradientId="fundLayerGrad"
          primaryLabel="NAV"
          showAverage
          showMinMax
          yAxisFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v))}
        />
      </Panel>
      <Panel title="جدول لایه‌ها" desc={`۱۵ روز آخر از ${points.length} روز موجود`}>
        <DataTable
          rows={points.slice(-15).reverse() as unknown as Record<string, unknown>[]}
          columns={[
            { key: "date", label: "تاریخ", render: (r) => <span dir="ltr">{fmtDate(r.date)}</span> },
            { key: "nav_issue", label: "صدور", render: (r) => <span dir="ltr">{fmt(r.nav_issue, 2)}</span> },
            { key: "nav_redemption", label: "ابطال", render: (r) => <span dir="ltr">{fmt(r.nav_redemption, 2)}</span> },
            { key: "nav_statistical", label: "آماری", render: (r) => <span dir="ltr">{fmt(r.nav_statistical, 2)}</span> },
            {
              key: "gap",
              label: "شکاف صدور/ابطال",
              render: (r) => {
                const i = Number(r.nav_issue);
                const d = Number(r.nav_redemption);
                if (!Number.isFinite(i) || !Number.isFinite(d) || !d) return "—";
                const g = ((i - d) / d) * 100;
                return <span className={g >= 0 ? "text-accent-emerald" : "text-accent-rose"} dir="ltr">{fmtPct(g)}</span>;
              },
            },
          ]}
          maxHeight={340}
        />
        <SourceNote>
          <code>/funds/v2/{symbol}/nav-history</code> — تاریخچه با Gap-Filling خودکار؛ سرچشمه: رکوردهای صدور/ابطال BrsApi و
          اسنپ‌شات روزانه.
        </SourceNote>
      </Panel>
    </div>
  );
}

// ── ۳. موتور NAV مستقل ──────────────────────────────────────────────────────

export function NavEngineTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useNavDashboard(symbol);
  if (isPending) return <Loading rows={5} />;
  if (!data) return <Empty text="موتور NAV پاسخی نداد" icon={Cpu} />;

  return (
    <div className="space-y-4">
      <Panel
        title="آخرین اجرای موتور NAV"
        desc="محاسبه مستقل و نسخه‌دار NAV به‌ازای هر نماد — مسیر فرمول بر اساس طبقه دارایی انتخاب می‌شود."
        actions={
          <div className="flex items-center gap-2">
            <Chip label={`نسخه موتور ${data.engine_version ?? "—"}`} tone="muted" />
            <RunButton kind="calculate" symbol={symbol} />
          </div>
        }
      >
        {data.latest_run ? <KeyValue data={data.latest_run as unknown as Record<string, unknown>} /> : <Empty text="هنوز اجرایی ثبت نشده — دکمه «اجرای محاسبه NAV» را بزنید." />}
      </Panel>
      <Panel title="تاریخچه اجراها" desc="۱۰ اجرای اخیر با کیفیت ورودی، پوشش و NAV واحد">
        <DataTable
          rows={(data.recent_runs ?? []) as unknown as Record<string, unknown>[]}
          columns={[
            { key: "valuation_date", label: "تاریخ ارزش‌گذاری", render: (r) => <span dir="ltr">{fmtDate(r.valuation_date)}</span> },
            { key: "nav_type", label: "نوع NAV", render: (r) => <Chip label={String(r.nav_type ?? "—")} tone="muted" /> },
            { key: "quality_status", label: "کیفیت ورودی", render: (r) => <Chip label={labelOf(QUALITY_LABELS, String(r.quality_status))} tone={qualityTone(String(r.quality_status)) === "pos" ? "pos" : qualityTone(String(r.quality_status)) === "neg" ? "neg" : "warn"} /> },
            { key: "coverage_pct", label: "پوشش", render: (r) => <span dir="ltr">{fmt(r.coverage_pct, 1)}٪</span> },
            { key: "nav_per_unit", label: "NAV واحد", render: (r) => <span dir="ltr" className="font-bold text-surface-100">{fmt(r.nav_per_unit)}</span> },
            { key: "net_assets", label: "دارایی خالص", render: (r) => <span dir="ltr">{fmtBig(r.net_assets)}</span> },
            { key: "units_outstanding", label: "واحدها", render: (r) => <span dir="ltr">{fmtBig(r.units_outstanding)}</span> },
            { key: "positions_count", label: "پوزیشن", render: (r) => <span dir="ltr">{fmt(r.positions_count)}</span> },
            { key: "engine_version", label: "نسخه موتور", render: (r) => <span dir="ltr" className="font-mono text-[10px]">{String(r.engine_version ?? "—")}</span> },
          ]}
          maxHeight={300}
          dense
        />
      </Panel>
      <SourceNote>
        <code>/funds/v2/nav/{symbol}/dashboard</code> — بسته یکپارچه موتور NAV و تطبیق.
      </SourceNote>
    </div>
  );
}

// ── ۴. تطبیق و مغایرت‌ها ────────────────────────────────────────────────────

export function ReconciliationTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useNavDashboard(symbol);
  if (isPending) return <Loading rows={5} />;
  const breaks = data?.open_breaks ?? [];

  return (
    <div className="space-y-4">
      <Panel
        title="آخرین تطبیق با مرجع"
        desc="مقایسه NAV مستقل با NAV منتشرشده؛ انحراف بیش از آستانه، مغایرت باز می‌کند."
        actions={<RunButton kind="reconcile" symbol={symbol} />}
      >
        {data?.latest_reconciliation ? <KeyValue data={data.latest_reconciliation as unknown as Record<string, unknown>} /> : <Empty text="تطبیقی ثبت نشده است" />}
      </Panel>

      <Panel
        title="پرونده‌های مغایرت باز"
        desc={`${breaks.length} مورد باز`}
        actions={<Chip label={breaks.length ? "نیازمند بررسی" : "بدون مغایرت"} tone={breaks.length ? "neg" : "pos"} />}
      >
        <DataTable
          rows={breaks as unknown as Record<string, unknown>[]}
          columns={[
            { key: "break_id", label: "پرونده", render: (r) => <span dir="ltr" className="font-mono">{fmt(r.break_id)}</span> },
            { key: "lifecycle", label: "چرخه", render: (r) => <Chip label={labelOf(BREAK_LIFECYCLE_LABELS, String(r.lifecycle))} tone={r.lifecycle === "RESOLVED" || r.lifecycle === "ACCEPTED" ? "pos" : r.lifecycle === "ESCALATED" ? "neg" : "warn"} /> },
            { key: "severity", label: "شدت", render: (r) => <Chip label={String(r.severity ?? "—")} tone={String(r.severity).startsWith("P0") ? "neg" : "warn"} /> },
            { key: "owner", label: "مسئول", render: (r) => <span className="text-surface-300">{String(r.owner ?? "—")}</span> },
            { key: "opened_at", label: "باز شدن", render: (r) => <span dir="ltr">{fmtDate(r.opened_at)}</span> },
            { key: "sla_due_at", label: "مهلت SLA", render: (r) => <span dir="ltr">{fmtDate(r.sla_due_at)}</span> },
            { key: "notes", label: "یادداشت", render: (r) => <span className="text-surface-400">{String(r.notes ?? "—")}</span> },
          ]}
          maxHeight={300}
          emptyText="مغایرت بازی وجود ندارد"
        />
      </Panel>

      <Panel title="سابقه تطبیق" desc="۱۰ تطبیق اخیر">
        <DataTable
          rows={(data?.reconciliation_history ?? []) as unknown as Record<string, unknown>[]}
          columns={[
            { key: "valuation_date", label: "تاریخ", render: (r) => <span dir="ltr">{fmtDate(r.valuation_date)}</span> },
            { key: "internal_nav", label: "NAV داخلی", render: (r) => <span dir="ltr">{fmt(r.internal_nav)}</span> },
            { key: "reference_nav", label: "NAV مرجع", render: (r) => <span dir="ltr">{fmt(r.reference_nav)}</span> },
            { key: "bps_diff", label: "اختلاف", render: (r) => <span dir="ltr" className="font-bold">{formatBps(Number(r.bps_diff))}</span> },
            { key: "diff_status", label: "نتیجه", render: (r) => <Chip label={labelOf(DIFF_LABELS, String(r.diff_status))} tone={diffTone(String(r.diff_status)) === "pos" ? "pos" : diffTone(String(r.diff_status)) === "neg" ? "neg" : "warn"} /> },
            { key: "comparability_status", label: "قابلیت مقایسه", render: (r) => <Chip label={labelOf(COMPARABILITY_LABELS, String(r.comparability_status))} tone="muted" /> },
            { key: "reference_status", label: "اعتبار مرجع", render: (r) => <Chip label={labelOf(REFERENCE_LABELS, String(r.reference_status))} tone={referenceTone(String(r.reference_status)) === "pos" ? "pos" : referenceTone(String(r.reference_status)) === "neg" ? "neg" : "warn"} /> },
          ]}
          maxHeight={280}
          dense
        />
      </Panel>
      <SourceNote>
        <code>/funds/v2/nav/{symbol}/reconciliation</code> و <code>/breaks</code> — چرخه عمر مغایرت از باز تا بسته.
      </SourceNote>
    </div>
  );
}

// ── ۵. NAV طبقاتی ───────────────────────────────────────────────────────────

export function ClassNavTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useClassNav(symbol);
  if (isPending) return <Loading rows={3} />;
  if (!data) return <Empty text="تخصیص طبقاتی ثبت نشده" icon={Network} />;

  const classes = (Array.isArray(data) ? data : ((data.classes ?? data.rows ?? data.allocations) as unknown)) as
    | Record<string, unknown>[]
    | undefined;

  return (
    <Panel title="تخصیص NAV طبقاتی" desc="توزیع NAV بین طبقات یک صندوق (نوع تخصیص ساده یا طبق‌به‌طبق) با پیکربندی نسخه‌دار.">
      {Array.isArray(classes) && classes.length ? (
        <DataTable rows={classes} />
      ) : (
        <KeyValue data={data as Record<string, unknown>} />
      )}
      <SourceNote>
        <code>/funds/v2/nav/{symbol}/class-nav</code> — پیکربندی طبقات از طریق <code>PUT …/class-nav/config</code> ثبت و نسخه‌گذاری
        می‌شود.
      </SourceNote>
    </Panel>
  );
}

// ── ۶. فراصندوق ─────────────────────────────────────────────────────────────

export function FofTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundFof(symbol);
  if (isPending) return <Loading rows={3} />;
  if (!data) return <Empty text="داده فراصندوق موجود نیست" icon={Network} />;

  const positions = data.positions ?? [];
  const summary = data.summary;

  return (
    <div className="space-y-4">
      <Panel title="ارزش‌گذاری فراصندوق" desc="NAV این صندوق از NAV زیرصندوق‌هایش ساخته می‌شود؛ حلقه‌های مرجع‌دهی باید شناسایی شوند.">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="تاریخ ارزش‌گذاری" value={fmtDate(data.valuation_date)} numeric={false} />
          <Stat label="ارزش کل" value={fmtBig(summary?.total_value)} />
          <Stat label="ارزش حلقوی" value={fmtBig(summary?.circular_value)} tone={hasCircularExposure(data) ? "neg" : "pos"} />
          <Stat label="پوزیشن ارزش‌گذاری‌شده" value={`${fmt(summary?.valued_positions)} / ${fmt((summary?.valued_positions ?? 0) + (summary?.missing_positions ?? 0))}`} />
          <Stat label="پوشش" value={`${fmt(summary?.coverage_pct, 1)}٪`} tone={(summary?.coverage_pct ?? 0) >= 90 ? "pos" : "warn"} />
        </div>
      </Panel>
      {positions.length > 0 && (
        <Panel title="زیرصندوق‌ها و حلقه‌های مرجع‌دهی" desc={`${positions.length} پوزیشن`}>
          <DataTable
            rows={positions as unknown as Record<string, unknown>[]}
            columns={[
              { key: "sub_fund_id", label: "زیرصندوق", render: (r) => <span className="font-bold text-surface-100">{String(r.sub_fund_id)}</span> },
              { key: "units", label: "واحدها", render: (r) => <span dir="ltr">{fmtBig(r.units)}</span> },
              { key: "sub_nav_per_unit", label: "NAV زیرصندوق", render: (r) => <span dir="ltr">{fmt(r.sub_nav_per_unit)}</span> },
              { key: "value", label: "ارزش", render: (r) => <span dir="ltr" className="font-bold">{fmtBig(r.value)}</span> },
              { key: "circular_flag", label: "حلقه", render: (r) => <Chip label={r.circular_flag ? "در حلقه" : "بدون حلقه"} tone={circularTone(Boolean(r.circular_flag)) === "neg" ? "neg" : "pos"} /> },
            ]}
          />
        </Panel>
      )}
      <SourceNote>
        <code>/funds/v2/nav/{symbol}/fof</code> — محاسبه از طریق <code>POST …/fof/calculate</code>.
      </SourceNote>
    </div>
  );
}

// ── ۷. مدارک و پذیرش سایه ───────────────────────────────────────────────────

export function NavEvidenceTab({ symbol }: { symbol: string }) {
  const evidence = useNavEvidence(symbol);
  const shadow = useShadowAcceptance(symbol);
  if (evidence.isPending) return <Loading rows={4} />;

  const items = (evidence.data?.items ?? evidence.data?.documents ?? []) as Record<string, unknown>[] | undefined;

  return (
    <div className="space-y-4">
      <Panel title="بسته مدارک NAV" desc="ردپای تغییرناپذیر هر محاسبه: ورودی‌ها، نسخه موتور، و خروجی امضاشده برای حسابرسی.">
        {Array.isArray(items) && items.length ? (
          <DataTable rows={items} />
        ) : evidence.data ? (
          <KeyValue data={evidence.data as Record<string, unknown>} />
        ) : (
          <Empty text="مدارکی ثبت نشده" />
        )}
      </Panel>
      <Panel title="پذیرش اجرای سایه" desc="سنجه‌های مقایسه اجرای سایه با نسخه رسمی، پیش از فعال‌سازی نماد.">
        {shadow.data ? <KeyValue data={shadow.data as Record<string, unknown>} /> : <Empty text="گزارش سایه موجود نیست" hint="این گزارش پس از اولین اجرای سایه تولید می‌شود." />}
      </Panel>
      <SourceNote>
        <code>/funds/v2/nav/{symbol}/evidence</code> و <code>/shadow-acceptance</code>.
      </SourceNote>
    </div>
  );
}
