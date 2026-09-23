"use client";

/**
 * Ledger, compliance/governance, data-quality and audit tabs.
 *
 * Most of these payloads are record lists whose exact columns depend on what
 * has been registered for the fund, so they render through one generic
 * resource view: the table shows the fields the API actually returned.
 */

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiPost } from "@/lib/api";
import {
  fundIdOf,
  useAccessLogs,
  useComplianceResource,
  useFundAliases,
  useFundCoverage,
  useFundMonitoring,
  useFundQuarantine,
  useLedgerEntries,
  useTrialBalance,
  useUnitMovements,
  useRegulatorEvidence,
  useGlobalCompliance,
} from "@/lib/fund-queries";
import { Chip, DataTable, Empty, fmt, fmtBig, fmtDate, FreshnessChip, KeyValue, Loading, Panel, rowsOf, SourceNote, Stat, StatGrid } from "@/components/funds/ui";
import { ACCOUNT_TYPE_LABELS, ENTRY_STATUS_LABELS, MOVEMENT_TYPE_LABELS, accountTone, movementTone } from "@/lib/fund-ledger";
import type { Tone as LibTone } from "@/lib/fund-nav";

const ACCOUNT_TONE: Record<LibTone, "pos" | "warn" | "neg" | "muted"> = {
  pos: "pos",
  warn: "warn",
  neg: "neg",
  default: "muted",
};
import {
  ArrowLeftRight,
  BookOpen,
  GitBranch,
  History,
  Receipt,
  ScrollText,
  UserCheck,
} from "lucide-react";

// ══════════════ گروه دفتری ══════════════

export function TrialBalanceTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useTrialBalance(symbol);
  if (isPending) return <Loading rows={5} />;
  const rows = (data?.accounts ?? []) as unknown as Record<string, unknown>[];
  const balanced = Boolean(data?.balanced);

  return (
    <Panel title="تراز آزمایشی" desc="جمع بدهکار و بستانکار هر حساب — برابر نبودن دو طرف یعنی دفتر هنوز بسته نشده است.">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-3">
        <Stat label="جمع بدهکار" value={fmtBig(data?.total_debit)} />
        <Stat label="جمع بستانکار" value={fmtBig(data?.total_credit)} />
        <Stat label="تعادل دفتر" value={balanced ? "برقرار" : "نابرابر"} tone={balanced ? "pos" : "neg"} />
      </div>
      {rows.length ? (
        <DataTable
          rows={rows}
          columns={[
            { key: "account_code", label: "کد حساب", render: (r) => <span dir="ltr" className="font-mono">{String(r.account_code ?? "—")}</span> },
            { key: "account_name", label: "عنوان حساب", render: (r) => <span className="text-surface-100">{String(r.account_name ?? "—")}</span> },
            { key: "account_type", label: "نوع", render: (r) => <Chip label={ACCOUNT_TYPE_LABELS[String(r.account_type)] ?? String(r.account_type ?? "—")} tone={ACCOUNT_TONE[accountTone(String(r.account_type))] ?? "muted"} /> },
            { key: "debit", label: "بدهکار", render: (r) => <span dir="ltr">{fmtBig(r.debit)}</span> },
            { key: "credit", label: "بستانکار", render: (r) => <span dir="ltr">{fmtBig(r.credit)}</span> },
            { key: "balance", label: "مانده", render: (r) => <span dir="ltr" className="font-bold text-surface-100">{fmtBig(r.balance)}</span> },
          ]}
          maxHeight={430}
        />
      ) : (
        <Empty text="سندی در دفتر این صندوق ثبت نشده" hint="اسناد از ثبت حرکت واحدها یا ورود دستی تولید می‌شوند." icon={BookOpen} />
      )}
      <SourceNote>
        <code>/funds/v2/ledger/{fundIdOf(symbol)}/trial-balance</code>
      </SourceNote>
    </Panel>
  );
}

export function EntriesTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useLedgerEntries(symbol);
  if (isPending) return <Loading rows={5} />;
  const rows = rowsOf(data, "entries", "items", "rows");
  if (!rows.length) return <Empty text="سند مالی ثبت نشده" icon={Receipt} />;

  return (
    <Panel title="اسناد مالی دوطرفه" desc={`${rows.length} سند — هر سند باید جمع بدهکار و بستانکار برابر داشته باشد.`}>
      <DataTable
        rows={rows}
        columns={[
          { key: "entry_id", label: "سند", render: (r) => <span dir="ltr" className="font-mono">{fmt(r.entry_id)}</span> },
          { key: "event_type", label: "رویداد", render: (r) => <Chip label={String(r.event_type ?? "—")} tone="muted" /> },
          { key: "status", label: "وضعیت", render: (r) => <Chip label={ENTRY_STATUS_LABELS[String(r.status)] ?? String(r.status ?? "—")} tone={r.status === "POSTED" ? "pos" : "warn"} /> },
          { key: "effective_at", label: "تاریخ اثر", render: (r) => <span dir="ltr">{fmtDate(r.effective_at)}</span> },
          { key: "source_system", label: "سامانه", render: (r) => <span className="text-surface-400">{String(r.source_system ?? "—")}</span> },
          { key: "memo", label: "شرح", render: (r) => <span className="text-surface-300">{String(r.memo ?? "—")}</span> },
          { key: "lines", label: "گردوها", render: (r) => <span dir="ltr">{Array.isArray(r.lines) ? r.lines.length.toLocaleString("fa-IR") : "—"}</span> },
        ]}
        maxHeight={470}
      />
      <SourceNote>
        سند برگشتی با <code>POST /funds/v2/ledger/entries/&#123;id&#125;/reverse</code> ثبت می‌شود؛ اسناد ثبت‌شده
        هرگز حذف نمی‌شوند.
      </SourceNote>
    </Panel>
  );
}

export function UnitMovementsTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useUnitMovements(symbol);
  if (isPending) return <Loading rows={5} />;
  const rows = rowsOf(data, "movements", "items", "rows");
  if (!rows.length) return <Empty text="حرکت واحدی ثبت نشده" hint="صدور و ابطال واحد، منبع اصلی ورودی این جدول است." icon={ArrowLeftRight} />;

  const net = rows.reduce((s, r) => s + Number(r.units ?? r.quantity ?? r.amount ?? 0), 0);

  return (
    <Panel
      title="حرکت واحدهای سرمایه‌گذاری"
      desc="ورود و خروج واحد و سند دوطرفه‌ای که به‌ازای هر حرکت ساخته می‌شود"
      actions={<Chip label={`خالص ${fmtBig(Math.abs(net))} واحد`} tone={net >= 0 ? "pos" : "neg"} />}
    >
      <DataTable
        rows={rows}
        columns={[
          { key: "movement_date", label: "تاریخ", render: (r) => <span dir="ltr">{fmtDate(r.movement_date)}</span> },
          {
            key: "movement_type",
            label: "نوع حرکت",
            render: (r) => (
              <Chip
                label={MOVEMENT_TYPE_LABELS[String(r.movement_type)] ?? String(r.movement_type ?? "—")}
                tone={movementTone(String(r.movement_type)) === "pos" ? "pos" : movementTone(String(r.movement_type)) === "warn" ? "warn" : "muted"}
              />
            ),
          },
          { key: "units", label: "واحدها", render: (r) => <span dir="ltr" className="font-bold">{fmtBig(r.units)}</span> },
          { key: "price_per_unit", label: "قیمت واحد", render: (r) => <span dir="ltr">{fmt(r.price_per_unit)}</span> },
          { key: "amount", label: "مبلغ", render: (r) => <span dir="ltr">{fmtBig(r.amount)}</span> },
          { key: "nav_type", label: "نوع NAV", render: (r) => <span className="text-surface-400">{String(r.nav_type ?? "—")}</span> },
          { key: "reference", label: "مرجع", render: (r) => <span dir="ltr" className="font-mono text-[10px]">{String(r.reference ?? "—")}</span> },
        ]}
        maxHeight={440}
      />
      <SourceNote>
        <code>/funds/v2/ledger/{fundIdOf(symbol)}/unit-movements</code> — ثبت جدید با POST همان مسیر.
      </SourceNote>
    </Panel>
  );
}

// ══════════════ گروه انطباق و حاکمیت ══════════════

interface ResourceSpec {
  title: string;
  desc: string;
  resource: string;
  global?: boolean;
  emptyText?: string;
}

function ComplianceResource({ symbol, spec }: { symbol: string; spec: ResourceSpec }) {
  const perFund = useComplianceResource(symbol, spec.global ? "" : spec.resource);
  const global = useGlobalCompliance(spec.global ? spec.resource : "");
  const { data, isPending } = spec.global ? global : perFund;
  if (isPending) return <Loading rows={4} />;
  const rows = rowsOf(data, "items", "rows", "records", "alerts", "approvals", "statements", "events", "rules", "complaints");
  if (!rows.length) return <Empty text={spec.emptyText ?? "رکوردی ثبت نشده"} hint={spec.desc} icon={ScrollText} />;

  return (
    <Panel title={spec.title} desc={spec.desc}>
      <DataTable rows={rows} maxHeight={450} />
      <SourceNote>
        <code>/funds/v2/compliance/{spec.global ? "" : `${fundIdOf(symbol)}/`}{spec.resource}</code>
      </SourceNote>
    </Panel>
  );
}

export const COMPLIANCE_SPECS: Record<string, ResourceSpec> = {
  aml: { title: "هشدارهای ضد پولشویی", desc: "الگوهای غیرعادی در حرکت نقدی و واحد، با شدت و وضعیت.", resource: "aml/alerts", emptyText: "هشداری تولید نشده" },
  str: { title: "گزارش معاملات مشکوک", desc: "STRهای ثبت‌شده و وضعیت ارسال به واحد اطلاعات مالی.", resource: "aml/str", emptyText: "گزارش مشکوکی ثبت نشده" },
  internalAudits: { title: "گزارش‌های حسابرسی داخلی", desc: "یافته‌ها و اقدامات اصلاحی حسابرس داخلی.", resource: "internal-audits", emptyText: "گزارشی ثبت نشده" },
  disciplinary: { title: "پرونده‌های انتظامی", desc: "پرونده‌های تخلف و وضعیت رسیدگی.", resource: "disciplinary", emptyText: "پرونده‌ای ثبت نشده" },
  insurance: { title: "بیمه‌نامه مسئولیت", desc: "بیمه مدیران (D&O) و مسئولیت مدنی صندوق.", resource: "insurance", emptyText: "بیمه‌نامه‌ای ثبت نشده" },
  tax: { title: "مالیات", desc: "مالیات ثبت‌شده و خلاصه دوره‌ها — مالیات مقطوع از معاملات قابل محاسبه است.", resource: "tax/summary", emptyText: "مالیتی ثبت نشده" },
  taxRules: { title: "قواعد مالیاتی نسخه‌دار", desc: "نرخ‌ها و قواعدی که محاسبه مالیات از آن‌ها خوانده می‌شود (config-driven).", resource: "tax/rules", global: true, emptyText: "قاعده‌ای تعریف نشده" },
  sharia: { title: "تأییدهای شرعی", desc: "ابزارهای دارای تأیید هیئت شرعی و تاریخ اعتبار.", resource: "sharia/approvals", global: true, emptyText: "تأیید شرعی ثبت نشده" },
  rpt: { title: "معاملات با اشخاص وابسته", desc: "معاملات با اشخاص وابسته و سقفهای مجاز — مهم‌ترین منبع تعارض منافع.", resource: "rpt", emptyText: "معامله‌ای ثبت نشده" },
  complaints: { title: "شکایات", desc: "شکایات ثبت‌شده و وضعیت پاسخ‌دهی.", resource: "complaints", emptyText: "شکایتی ثبت نشده" },
  prospectus: { title: "نسخه‌های اساسنامه", desc: "تاریخچه اساسنامه و مصوبات مجمع — مبنای پارامترهای محاسبه NAV.", resource: "prospectus", emptyText: "نسخه‌ای ثبت نشده" },
  lifecycle: { title: "رویدادهای چرخه عمر", desc: "تأسیس، افزایش سرمایه، ادغام، انحلال و تغییرات مجاز.", resource: "lifecycle", emptyText: "رویدادی ثبت نشده" },
  csdi: { title: "مغایرت واحدها با سامانه ثبت", desc: "تطبیق تعداد واحدهای داخلی با صورت‌وضعیت CSDI.", resource: "csdi/breaks", emptyText: "مغایرتی وجود ندارد" },
};

export function GovernanceTab({ symbol }: { symbol: string }) {
  const committees = useComplianceResource(symbol, "committees");
  const audits = useComplianceResource(symbol, "internal-audits");
  const disciplinary = useComplianceResource(symbol, "disciplinary");
  const insurance = useComplianceResource(symbol, "insurance");

  const counts = [
    { label: "کمیته‌ها", rows: rowsOf(committees.data, "items", "committees"), tone: "accent" as const },
    { label: "حسابرسی داخلی", rows: rowsOf(audits.data, "items", "audits"), tone: "pos" as const },
    { label: "پرونده انتظامی", rows: rowsOf(disciplinary.data, "items", "cases"), tone: "neg" as const },
    { label: "بیمه‌نامه", rows: rowsOf(insurance.data, "items", "policies"), tone: "default" as const },
  ];

  return (
    <div className="space-y-4">
      <Panel title="ساختار حاکمیتی" desc="کمیتته، حسابرس داخلی، پرونده‌های انتظامی و بیمه مسئولیت مدیران">
        <StatGrid cols={4}>
          {counts.map((c) => (
            <Stat key={c.label} label={c.label} value={c.rows.length.toLocaleString("fa-IR")} tone={c.tone} />
          ))}
        </StatGrid>
      </Panel>
      <ComplianceBlock title="کمیته‌های حاکمیتی" desc="اعضا، نقش و تاریخ آخرین جلسه" rows={rowsOf(committees.data, "items", "committees")} pending={committees.isPending} />
      <ComplianceBlock title="گزارش‌های حسابرسی داخلی" rows={rowsOf(audits.data, "items", "audits")} pending={audits.isPending} />
      <ComplianceBlock title="پرونده‌های انتظامی" rows={rowsOf(disciplinary.data, "items", "cases")} pending={disciplinary.isPending} />
      <ComplianceBlock title="بیمه‌نامه‌های مسئولیت" rows={rowsOf(insurance.data, "items", "policies")} pending={insurance.isPending} />
      <SourceNote>
        <code>/funds/v2/compliance/{fundIdOf(symbol)}/&#123;committees|internal-audits|disciplinary|insurance&#125;</code>
      </SourceNote>
    </div>
  );
}

function ComplianceBlock({ title, rows, pending, desc }: { title: string; rows: Record<string, unknown>[]; pending: boolean; desc?: string }) {
  return (
    <Panel title={title} desc={desc}>
      {pending ? <Loading rows={3} /> : rows.length ? <DataTable rows={rows} maxHeight={280} dense /> : <Empty text="رکوردی ثبت نشده" />}
    </Panel>
  );
}

export function ComplianceTab({ symbol }: { symbol: string }) {
  const aml = useComplianceResource(symbol, "aml/alerts");
  const rpt = useComplianceResource(symbol, "rpt");
  const lifecycle = useComplianceResource(symbol, "lifecycle");
  const alerts = rowsOf(aml.data, "items", "alerts");
  const openAlerts = alerts.filter((a) => String(a.status ?? "").toUpperCase() !== "CLOSED");

  return (
    <div className="space-y-4">
      <Panel
        title="وضعیت انطباق"
        desc="خلاصه هشدارها، معاملات با اشخاص وابسته و رویدادهای چرخه عمر"
        actions={<Chip label={`${openAlerts.length} هشدار باز`} tone={openAlerts.length ? "neg" : "pos"} dot={openAlerts.length > 0} />}
      >
        <StatGrid cols={3}>
          <Stat label="هشدارهای AML" value={alerts.length.toLocaleString("fa-IR")} tone={alerts.length ? "warn" : "pos"} />
          <Stat label="معاملات وابسته" value={rowsOf(rpt.data, "items", "transactions").length.toLocaleString("fa-IR")} />
          <Stat label="رویداد چرخه عمر" value={rowsOf(lifecycle.data, "items", "events").length.toLocaleString("fa-IR")} />
        </StatGrid>
      </Panel>
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.aml} />
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.rpt} />
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.lifecycle} />
    </div>
  );
}

export function AmlTab({ symbol }: { symbol: string }) {
  return (
    <div className="space-y-4">
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.aml} />
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.str} />
    </div>
  );
}

export function TaxTab({ symbol }: { symbol: string }) {
  return (
    <div className="space-y-4">
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.tax} />
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.taxRules} />
    </div>
  );
}

export function GovernanceDocsTab({ symbol }: { symbol: string }) {
  return (
    <div className="space-y-4">
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.prospectus} />
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.sharia} />
      <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.complaints} />
    </div>
  );
}

export function CsdiTab({ symbol }: { symbol: string }) {
  return <ComplianceResource symbol={symbol} spec={COMPLIANCE_SPECS.csdi} />;
}

// ══════════════ گروه کیفیت داده ══════════════

const COVERAGE_STATUS: Record<string, { label: string; tone: "pos" | "warn" | "neg" | "muted" }> = {
  ok: { label: "سالم", tone: "pos" },
  partial: { label: "ناقص", tone: "warn" },
  stale: { label: "کهنه", tone: "neg" },
  missing: { label: "غایب", tone: "muted" },
};

export function CoverageTab({ symbol }: { symbol: string }) {
  const [status, setStatus] = useState<string | undefined>();
  const { data, isPending } = useFundCoverage(status);
  const rows = useMemo(() => {
    const all = data?.items ?? [];
    const mine = all.filter((r) => String(r.symbol ?? "").toUpperCase() === symbol.toUpperCase());
    return { mine, rest: all };
  }, [data, symbol]);

  if (isPending) return <Loading rows={5} />;

  return (
    <div className="space-y-4">
      <Panel
        title="پوشش و تازگی داده"
        desc="چه تعدادی از روزهای معاملاتی برای هر صندوق داده NAV و قیمت دارند"
        actions={
          <div className="flex gap-1 flex-wrap">
            {(["", "ok", "partial", "stale", "missing"] as const).map((s) => (
              <button
                key={s || "all"}
                onClick={() => setStatus(s || undefined)}
                className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-colors ${
                  (status ?? "") === s ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                }`}
              >
                {s === "" ? "همه" : COVERAGE_STATUS[s]?.label ?? s}
                {data?.summary?.[s] !== undefined && ` (${data.summary[s].toLocaleString("fa-IR")})`}
              </button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {Object.entries(data?.summary ?? {}).map(([k, v]) => {
            const meta = COVERAGE_STATUS[k] ?? { label: k, tone: "muted" as const };
            return <Stat key={k} label={`وضعیت ${meta.label}`} value={(v as number).toLocaleString("fa-IR")} tone={meta.tone} />;
          })}
        </div>
        {rows.mine.length > 0 && (
          <div className="mb-4">
            <p className="text-[11px] text-surface-400 mb-2">وضعیت همین صندوق:</p>
            <DataTable rows={rows.mine as unknown as Record<string, unknown>[]} />
          </div>
        )}
        <DataTable rows={rows.rest as unknown as Record<string, unknown>[]} maxHeight={400} />
      </Panel>
      <SourceNote>
        <code>/funds/v2/coverage</code> — KPI پوشش (A6). صندوق غایب یعنی هنوز در Universe کشف نشده یا اسنپ‌شات آن
        نرسیده است.
      </SourceNote>
    </div>
  );
}

export function QuarantineTab({ symbol }: { symbol: string }) {
  const qc = useQueryClient();
  const [reviewed, setReviewed] = useState(false);
  const { data, isPending } = useFundQuarantine(reviewed);
  const rows = useMemo(() => {
    const all = data?.items ?? [];
    const mine = all.filter((r) => String(r.fund_id ?? "").toUpperCase().includes(symbol.toUpperCase()));
    return [...mine, ...all.filter((r) => !mine.includes(r))];
  }, [data, symbol]);

  async function markReviewed(id: unknown) {
    try {
      await apiPost(`/funds/v2/quarantine/${encodeURIComponent(String(id))}/review`);
      toast.success("رکورد بازبینی‌شده علامت خورد");
      qc.invalidateQueries({ queryKey: ["funds", "v2", "quarantine"] });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "بازبینی ثبت نشد");
    }
  }

  return (
    <Panel
      title="داده‌های قرنطینه‌شده"
      desc="رکوردهایی که قواعد اعتبارسنجی ورودی را رد کرده‌اند؛ بازرسی آن‌ها تکلیف داده را مشخص می‌کند."
      actions={
        <div className="flex gap-1">
          {[false, true].map((v) => (
            <button
              key={String(v)}
              onClick={() => setReviewed(v)}
              className={`text-[10px] px-2 py-1 rounded-lg font-bold ${reviewed === v ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"}`}
            >
              {v ? "بازبینی‌شده" : "بازبینی‌نشده"}
            </button>
          ))}
        </div>
      }
    >
      {isPending ? (
        <Loading rows={4} />
      ) : rows.length === 0 ? (
        <Empty text={reviewed ? "رکورد بازبینی‌شده‌ای نیست" : "هیچ داده رد‌شده‌ای وجود ندارد"} hint="یعنی قواعد اعتبارسنجی، ورودی‌ای را رد نکرده‌اند." icon={UserCheck} />
      ) : (
        <DataTable
          rows={rows}
          columns={[
            { key: "created_at", label: "زمان", render: (r) => <span dir="ltr">{fmtDate(r.created_at)}</span> },
            { key: "source_endpoint", label: "منبع", render: (r) => <code className="text-[10px] text-surface-400">{String(r.source_endpoint ?? "—")}</code> },
            { key: "fund_id", label: "صندوق", render: (r) => <span className="text-surface-200">{String(r.fund_id ?? "—")}</span> },
            { key: "reject_rule", label: "قاعده", render: (r) => <Chip label={String(r.reject_rule ?? "—")} tone="warn" /> },
            { key: "reject_reason", label: "دلیل", render: (r) => <span className="text-surface-400">{String(r.reject_reason ?? "—")}</span> },
            {
              key: "action",
              label: "اقدام",
              render: (r) =>
                reviewed ? (
                  <Chip label="بازبینی شد" tone="pos" />
                ) : (
                  <button
                    onClick={() => void markReviewed(r.id)}
                    className="text-[10px] px-2 py-1 rounded-lg bg-accent-emerald/15 text-accent-emerald hover:bg-accent-emerald/25 transition-colors font-bold"
                  >
                    علامت بازبینی
                  </button>
                ),
            },
          ]}
          maxHeight={430}
        />
      )}
      <SourceNote>
        <code>/funds/v2/quarantine?reviewed={String(reviewed)}</code> — خطای یک صندوق، همگام‌سازی بقیه را متوقف نمی‌کند.
      </SourceNote>
    </Panel>
  );
}

export function AliasesTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundAliases(symbol);
  const rows = data?.aliases ?? [];
  return (
    <Panel title="نام‌های مستعار و تغییر نماد" desc="سابقه نماد، ISIN و کد ملی یک صندوق — برای پیوستگی تاریخچه پس از ادغام یا تغییر نماد.">
      {isPending ? (
        <Loading rows={3} />
      ) : rows.length ? (
        <DataTable
          rows={rows as unknown as Record<string, unknown>[]}
          columns={[
            { key: "symbol", label: "نماد", render: (r) => <span className="font-bold text-surface-100">{String(r.symbol)}</span> },
            { key: "isin", label: "ISIN", render: (r) => <span dir="ltr" className="font-mono text-[10px]">{String(r.isin ?? "—")}</span> },
            { key: "national_id", label: "کد ملی", render: (r) => <span dir="ltr">{String(r.national_id ?? "—")}</span> },
            { key: "source", label: "منبع", render: (r) => <Chip label={String(r.source ?? "—")} tone="muted" /> },
            { key: "is_active", label: "فعال", render: (r) => <Chip label={r.is_active ? "فعال" : "منقضی"} tone={r.is_active ? "pos" : "muted"} /> },
            { key: "first_seen_at", label: "اولین مشاهده", render: (r) => <span dir="ltr">{fmtDate(r.first_seen_at)}</span> },
            { key: "last_seen_at", label: "آخرین مشاهده", render: (r) => <span dir="ltr">{fmtDate(r.last_seen_at)}</span> },
          ]}
        />
      ) : (
        <Empty text="نام مستعار دیگری ثبت نشده" hint="این جدول با کشف خودکار Universe پر می‌شود." icon={GitBranch} />
      )}
      <SourceNote>
        <code>/funds/v2/aliases/{fundIdOf(symbol)}</code>
      </SourceNote>
    </Panel>
  );
}

export function MonitoringTab() {
  const { data, isPending } = useFundMonitoring();
  if (isPending) return <Loading rows={4} />;
  if (!data) return <Empty text="متریک پایش بازنگشت" />;

  const d = data as Record<string, unknown>;
  return (
    <div className="space-y-4">
      <Panel title="سلامت ماژول صندوق‌ها" desc="شمارشگرهای سطح پایگاه داده — برای اینکه بدانید کدام بخش داده هنوز پر نشده است.">
        <StatGrid cols={3}>
          <Stat label="صندوق‌های ETF در Universe" value={fmt(d.universe_count)} tone="accent" />
          <Stat label="رکورد تاریخچه NAV" value={fmt(d.nav_history_rows)} />
          <Stat label="رکورد ترکیب دارایی" value={fmt(d.holdings_rows)} />
          <Stat label="امتیازهای دوره‌ای" value={fmt(d.scores_rows)} />
          <Stat label="قرنطینه بازبینی‌نشده" value={fmt(d.quarantine_unreviewed)} tone={Number(d.quarantine_unreviewed) ? "neg" : "pos"} />
          <Stat label="قیمت‌های کهنه (بیش از ۵ دقیقه)" value={fmt(d.stale_quotes)} tone={Number(d.stale_quotes) ? "warn" : "pos"} />
        </StatGrid>
        <div className="flex items-center gap-2 mt-4">
          <FreshnessChip value={Number(d.stale_quotes) > 0 ? "stale" : "live"} />
          <Chip label={`نسخه موتور ${String(d.engine_version ?? "—")}`} tone="muted" />
        </div>
      </Panel>
      <Panel title="جزئیات پاسخ پایش">
        <KeyValue data={d} />
      </Panel>
      <SourceNote>
        <code>/funds/v2/monitoring</code> — همين داده‌ها در تب «پایش داده» صفحه فهرست صندوق‌ها هم نمایش داده می‌شوند.
      </SourceNote>
    </div>
  );
}

// ══════════════ گروه حسابرسی ══════════════

export function AuditPackTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useRegulatorEvidence(symbol);
  if (isPending) return <Loading rows={4} />;
  const rows = rowsOf(data, "items", "documents", "evidence");
  const fid = fundIdOf(symbol);

  return (
    <div className="space-y-4">
      <Panel
        title="بسته مدارک نظارتی"
        desc="مجموعه‌ای از شواهد تغییرناپذیر که نشان می‌دهد هر عدد از کجا آمده است."
        actions={
          <a
            href={`/api/v1/funds/v2/regulator/${encodeURIComponent(fid)}/audit-pack`}
            target="_blank"
            rel="noreferrer"
            className="text-[11px] font-bold px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-200 border border-surface-700 transition-colors inline-flex items-center gap-1"
          >
            <span className="material-icons text-[13px]">download</span>
            دریافت CSV
          </a>
        }
      >
        {rows.length ? <DataTable rows={rows} maxHeight={400} /> : data ? <KeyValue data={data as Record<string, unknown>} /> : <Empty text="مدارکی ثبت نشده" />}
      </Panel>
      <SourceNote>
        <code>/funds/v2/regulator/{fid}/evidence</code> و <code>/audit-pack</code> (خروجی CSV).
      </SourceNote>
    </div>
  );
}

export function AccessLogTab() {
  const { data, isPending } = useAccessLogs();
  if (isPending) return <Loading rows={4} />;
  const rows = rowsOf(data, "items", "logs", "records");
  return (
    <Panel title="سابقه دسترسی نظارتی" desc="چه کسی، چه داده‌ای را و در چه تاریخی خوانده است — بخش ممیزی سیستم.">
      {rows.length ? <DataTable rows={rows} maxHeight={430} dense /> : <Empty text="سابقه‌ای ثبت نشده" hint="ثبت دسترسی‌ها با فعال‌شدن ماژول نظارت پر می‌شود." icon={History} />}
      <SourceNote>
        <code>/funds/v2/regulator/access-logs</code>
      </SourceNote>
    </Panel>
  );
}
