"use client";

/**
 * 🛡 FundCompliancePanel — انطباق و حاکمیت در صفحه صندوق.
 *
 * بخش‌ها: FOF (با هشدار حلقه) | مالیات | AML و STR | حاکمیت و چرخه عمر | CSDI
 */

import { useState } from "react";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import {
  useAmlAlerts,
  useCalculateFof,
  useCalculateTax,
  useCommittees,
  useComplaints,
  useCreateStr,
  useCsdiBreaks,
  useFofLatest,
  useGenerateAmlAlerts,
  useImportCsdiStatement,
  useLifecycleEvents,
  useProspectusVersions,
  useReconcileCsdi,
  useRptList,
  useStrReports,
  useTaxSummary,
} from "@/hooks/useFundCompliance";
import {
  COMMITTEE_LABELS,
  TAX_TYPE_LABELS,
  formatPct,
  hasCircularExposure,
  riskTone,
} from "@/lib/fund-compliance";
import { formatAmount } from "@/lib/fund-ledger";
import { labelOf, type Tone } from "@/lib/fund-nav";

const TONE_CLASS: Record<Tone, string> = {
  pos: "text-accent-emerald bg-accent-emerald/15",
  warn: "text-accent-amber bg-accent-amber/15",
  neg: "text-accent-rose bg-accent-rose/15",
  default: "text-surface-300 bg-surface-600/25",
};

function Chip({ label, tone = "default" }: { label: string; tone?: Tone }) {
  return (
    <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${TONE_CLASS[tone]}`}>
      {label}
    </span>
  );
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function FundCompliancePanel({ symbol }: { symbol: string }) {
  const [taxBase, setTaxBase] = useState("");
  const [strReason, setStrReason] = useState("");
  const [csdiDate, setCsdiDate] = useState(todayIso());
  const [csdiUnits, setCsdiUnits] = useState("");

  const fof = useFofLatest(symbol);
  const calcFof = useCalculateFof(symbol);
  const tax = useTaxSummary(symbol);
  const calcTax = useCalculateTax(symbol);
  const alerts = useAmlAlerts(symbol);
  const genAlerts = useGenerateAmlAlerts(symbol);
  const strs = useStrReports(symbol);
  const createStr = useCreateStr(symbol);
  const committees = useCommittees(symbol);
  const rpt = useRptList(symbol);
  const complaints = useComplaints(symbol);
  const prospectus = useProspectusVersions(symbol);
  const lifecycle = useLifecycleEvents(symbol);
  const csdiBreaks = useCsdiBreaks(symbol);
  const importCsdi = useImportCsdiStatement(symbol);
  const reconcileCsdi = useReconcileCsdi(symbol);

  async function handleFof() {
    try {
      await calcFof.mutateAsync();
      toast.success("ارزش فراصندوق محاسبه شد");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در محاسبه FOF");
    }
  }

  async function handleAlerts() {
    try {
      const result = await genAlerts.mutateAsync();
      toast.success(`هشدارها بررسی شد — ${result?.alerts_created ?? 0} هشدار جدید`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در تولید هشدار");
    }
  }

  async function handleTax() {
    const base = Number(taxBase);
    if (!base || base <= 0) {
      toast.error("مبلغ پایه معتبر وارد کنید");
      return;
    }
    try {
      await calcTax.mutateAsync({
        tax_type: "TRANSFER_05",
        base_amount: base,
        period_label: new Date().toISOString().slice(0, 7),
      });
      toast.success("مالیات محاسبه و ثبت شد");
      setTaxBase("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در محاسبه مالیات");
    }
  }

  async function handleStr() {
    if (strReason.trim().length < 3) {
      toast.error("دلیل گزارش را وارد کنید");
      return;
    }
    try {
      await createStr.mutateAsync({ reason: strReason });
      toast.success("گزارش مشکوک (DRAFT) ثبت شد");
      setStrReason("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در ثبت STR");
    }
  }

  async function handleCsdiImport() {
    const units = Number(csdiUnits);
    if (!units || units < 0) {
      toast.error("تعداد واحد CSDI را وارد کنید");
      return;
    }
    try {
      await importCsdi.mutateAsync({
        as_of_date: csdiDate,
        units_outstanding: units,
        source_ref: `manual-${csdiDate}`,
      });
      toast.success("صورت‌وضعیت CSDI ثبت شد");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در ثبت صورت‌وضعیت");
    }
  }

  async function handleCsdiReconcile() {
    try {
      const result = await reconcileCsdi.mutateAsync();
      if (result?.status === "BREACH") {
        toast.error(`مغایرت واحد: ${formatAmount(result.units_diff)}`);
      } else {
        toast.success("تطبیق واحدها با CSDI انجام شد");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در تطبیق CSDI");
    }
  }

  const fofData = fof.data;

  return (
    <Card
      title="انطباق، حاکمیت و چرخه عمر"
      actions={
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleFof}
            disabled={calcFof.isPending}
            className="text-[10px] font-bold text-primary-300 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg px-2 py-1 disabled:opacity-50"
          >
            {calcFof.isPending ? "..." : "محاسبه FOF"}
          </button>
          <button
            onClick={handleAlerts}
            disabled={genAlerts.isPending}
            className="text-[10px] font-bold text-accent-amber bg-accent-amber/10 hover:bg-accent-amber/20 border border-accent-amber/30 rounded-lg px-2 py-1 disabled:opacity-50"
          >
            {genAlerts.isPending ? "..." : "بررسی AML"}
          </button>
          <button
            onClick={handleCsdiReconcile}
            disabled={reconcileCsdi.isPending}
            className="text-[10px] font-bold text-accent-emerald bg-accent-emerald/10 hover:bg-accent-emerald/20 border border-accent-emerald/30 rounded-lg px-2 py-1 disabled:opacity-50"
          >
            {reconcileCsdi.isPending ? "..." : "تطبیق CSDI"}
          </button>
        </div>
      }
    >
      {fof.isLoading && <Skeleton className="h-20 w-full rounded-xl" />}

      {!fof.isLoading && (
        <>
          {/* FOF */}
          <div className="mb-4">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <p className="text-[11px] text-surface-400">فراصندوق (NAV از NAV زیرصندوق‌ها)</p>
              {hasCircularExposure(fofData) && <Chip label="حلقه حلقوی شناسایی شد" tone="neg" />}
              {fofData && (
                <Chip
                  label={`پوشش ${formatPct(fofData.summary?.coverage_pct)}`}
                  tone={(fofData.summary?.coverage_pct ?? 0) >= 95 ? "pos" : "warn"}
                />
              )}
            </div>
            {fofData ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="glass-card p-3">
                  <p className="text-[10px] text-surface-500 mb-1">ارزش کل زیرصندوق‌ها</p>
                  <p className="font-mono text-sm text-surface-100" dir="ltr">
                    {formatAmount(fofData.summary?.total_value)}
                  </p>
                </div>
                <div className="glass-card p-3">
                  <p className="text-[10px] text-surface-500 mb-1">ارزش حلقوی (جدا)</p>
                  <p className="font-mono text-sm text-accent-rose" dir="ltr">
                    {formatAmount(fofData.summary?.circular_value)}
                  </p>
                </div>
                <div className="glass-card p-3">
                  <p className="text-[10px] text-surface-500 mb-1">موقعیت‌های ارزش‌گذاری‌شده</p>
                  <p className="font-mono text-sm text-surface-100">{fofData.summary?.valued_positions ?? 0}</p>
                </div>
                <div className="glass-card p-3">
                  <p className="text-[10px] text-surface-500 mb-1">موقعیت بدون NAV</p>
                  <p className="font-mono text-sm text-accent-amber">{fofData.summary?.missing_positions ?? 0}</p>
                </div>
              </div>
            ) : (
              <p className="text-[10px] text-surface-600">موقعیت زیرصندوقی ثبت نشده است.</p>
            )}
          </div>

          {/* Tax */}
          <div className="mb-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <p className="text-[11px] text-surface-400">مالیات</p>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="ارزش فروش (ریال)"
                  value={taxBase}
                  onChange={(e) => setTaxBase(e.target.value)}
                  className="text-[10px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-1 text-surface-300 w-36"
                  dir="ltr"
                />
                <button
                  onClick={handleTax}
                  disabled={calcTax.isPending}
                  className="text-[10px] font-bold text-primary-300 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg px-2 py-1 disabled:opacity-50"
                >
                  محاسبه ۰.۵٪
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {(tax.data?.items ?? []).slice(0, 4).map((item) => (
                <div key={item.tax_id} className="bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
                  <span className="text-surface-400">{labelOf(TAX_TYPE_LABELS, item.tax_type)}: </span>
                  <span className="font-mono text-surface-100" dir="ltr">
                    {formatAmount(item.tax_amount)}
                  </span>
                  {item.exempt && <span className="text-accent-emerald mr-1"> (معاف)</span>}
                </div>
              ))}
              {(tax.data?.items?.length ?? 0) === 0 && (
                <p className="text-[10px] text-surface-600">محاسبه مالیاتی ثبت نشده است.</p>
              )}
            </div>
          </div>

          {/* AML */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-[11px] text-surface-400 mb-2">هشدارهای AML</p>
              <div className="space-y-1.5">
                {(alerts.data ?? []).slice(0, 4).map((a) => (
                  <div key={a.alert_id} className="flex items-center justify-between bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
                    <div className="flex items-center gap-2">
                      <Chip label={a.risk_level} tone={riskTone(a.risk_level)} />
                      <span className="text-surface-300">{a.alert_type}</span>
                    </div>
                    <span className="font-mono text-surface-300" dir="ltr">{formatAmount(a.amount)}</span>
                  </div>
                ))}
                {(alerts.data?.length ?? 0) === 0 && (
                  <p className="text-[10px] text-surface-600">هشداری ثبت نشده است.</p>
                )}
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-[11px] text-surface-400">گزارش مشکوک (STR)</p>
                <div className="flex items-center gap-1">
                  <input
                    placeholder="دلیل گزارش"
                    value={strReason}
                    onChange={(e) => setStrReason(e.target.value)}
                    className="text-[10px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-1 text-surface-300 w-32"
                  />
                  <button
                    onClick={handleStr}
                    disabled={createStr.isPending}
                    className="text-[10px] text-accent-rose bg-accent-rose/10 hover:bg-accent-rose/20 rounded-lg px-2 py-1 disabled:opacity-50"
                  >
                    ثبت
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                {(strs.data ?? []).slice(0, 3).map((s) => (
                  <div key={s.str_id} className="flex items-center justify-between bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
                    <span className="text-surface-300">{s.reason}</span>
                    <Chip label={s.status} tone={s.status === "SUBMITTED" ? "pos" : "warn"} />
                  </div>
                ))}
                {(strs.data?.length ?? 0) === 0 && (
                  <p className="text-[10px] text-surface-600">گزارشی ثبت نشده است.</p>
                )}
              </div>
            </div>
          </div>

          {/* Governance + lifecycle */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            <div className="bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
              <p className="text-surface-500 mb-1">کمیته‌ها</p>
              {(committees.data ?? []).length > 0 ? (
                (committees.data ?? []).map((c) => (
                  <p key={c.committee_id} className="text-surface-300">
                    {labelOf(COMMITTEE_LABELS, c.committee_type)}
                  </p>
                ))
              ) : (
                <p className="text-surface-600">ثبت نشده</p>
              )}
            </div>
            <div className="bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
              <p className="text-surface-500 mb-1">معاملات وابسته</p>
              <p className="font-mono text-surface-100">{rpt.data?.length ?? 0}</p>
            </div>
            <div className="bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
              <p className="text-surface-500 mb-1">شکایات</p>
              <p className="font-mono text-surface-100">{complaints.data?.length ?? 0}</p>
            </div>
            <div className="bg-surface-800/40 rounded-lg px-3 py-2 text-[10px]">
              <p className="text-surface-500 mb-1">نسخه‌های امیدنامه</p>
              <p className="font-mono text-surface-100">{prospectus.data?.length ?? 0}</p>
            </div>
          </div>

          {((lifecycle.data?.length ?? 0) > 0 || (prospectus.data?.length ?? 0) > 0) && (
            <div className="mb-4">
              <p className="text-[11px] text-surface-400 mb-2">آخرین رویدادهای چرخه عمر / امیدنامه</p>
              <div className="space-y-1">
                {(lifecycle.data ?? []).slice(0, 3).map((e, idx) => (
                  <div key={`lc-${idx}`} className="text-[10px] text-surface-400">
                    {String(e.event_type)} — {String(e.event_date)}
                  </div>
                ))}
                {(prospectus.data ?? []).slice(0, 2).map((p, idx) => (
                  <div key={`pr-${idx}`} className="text-[10px] text-surface-400">
                    امیدنامه {String(p.version)} ({String(p.change_type)})
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CSDI */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <p className="text-[11px] text-surface-400">تطبیق واحدها با CSDI</p>
              <div className="flex items-center gap-1">
                <input
                  type="date"
                  value={csdiDate}
                  onChange={(e) => setCsdiDate(e.target.value)}
                  className="text-[10px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-1 text-surface-300"
                  dir="ltr"
                />
                <input
                  type="number"
                  placeholder="واحد CSDI"
                  value={csdiUnits}
                  onChange={(e) => setCsdiUnits(e.target.value)}
                  className="text-[10px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-1 text-surface-300 w-28"
                  dir="ltr"
                />
                <button
                  onClick={handleCsdiImport}
                  disabled={importCsdi.isPending}
                  className="text-[10px] text-primary-300 bg-primary-600/10 hover:bg-primary-600/20 rounded-lg px-2 py-1 disabled:opacity-50"
                >
                  ثبت
                </button>
              </div>
            </div>
            {(csdiBreaks.data ?? []).slice(0, 3).map((b) => (
              <div key={b.break_id} className="flex items-center justify-between bg-surface-800/40 rounded-lg px-3 py-2 text-[10px] mb-1">
                <span className="text-surface-400">{b.as_of_date}</span>
                <span className="font-mono text-accent-rose" dir="ltr">
                  Δ {formatAmount(b.units_diff)}
                </span>
              </div>
            ))}
            {(csdiBreaks.data?.length ?? 0) === 0 && (
              <p className="text-[10px] text-surface-600">مغایرت واحدی ثبت نشده است.</p>
            )}
          </div>

          <p className="text-[10px] text-surface-600 mt-4">
            رکوردهای انطباق داخلی‌اند و جای سامانه‌های رسمی (مرکز AML/CSDI) را نمی‌گیرند؛
            برای ارائه رسمی، خروجی `export` و درگاه نظارتی استفاده می‌شود.
          </p>
        </>
      )}
    </Card>
  );
}
