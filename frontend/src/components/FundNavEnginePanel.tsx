"use client";

/**
 * 🧮 FundNavEnginePanel — پنل «NAV مستقل + تطبیق با مرجع» در صفحه صندوق.
 *
 * نمایش:
 *   - آخرین اجرای NAV مستقل (کیفیت داده، پوشش قیمت، خالص دارایی، NAV هر واحد)
 *   - آخرین تطبیق در سه بُعد جدا (مقایسه‌پذیری / اعتبار مرجع / اختلاف bps)
 *   - ردیف‌های ارزش‌گذاری (منبع قیمت و کیفیت هر ردیف)
 *   - پرونده‌های مغایرت باز با چرخه عمر
 *
 * اجرای محاسبه/تطبیق در حالت SHADOW است و هیچ سفارشی ارسال نمی‌کند.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import {
  useCalculateClassNav,
  useCalculateFundNav,
  useFundClassNav,
  useFundNavDashboard,
  useReconcileFundNav,
  useUpdateNavBreak,
} from "@/hooks/useFundNavEngine";
import {
  BREAK_LIFECYCLE_LABELS,
  COMPARABILITY_LABELS,
  DIFF_LABELS,
  QUALITY_LABELS,
  REFERENCE_LABELS,
  diffTone,
  formatBps,
  formatNav,
  labelOf,
  qualityTone,
  referenceTone,
  type Tone,
} from "@/lib/fund-nav";

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

function Stat({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
}) {
  const toneClass =
    tone === "pos"
      ? "text-accent-emerald"
      : tone === "warn"
        ? "text-accent-amber"
        : tone === "neg"
          ? "text-accent-rose"
          : "text-surface-100";
  return (
    <div className="glass-card p-3">
      <p className="text-[10px] text-surface-500 mb-1">{label}</p>
      <p className={`font-mono text-sm font-bold ${toneClass}`} dir="ltr" style={{ textAlign: "right" }}>
        {value}
      </p>
      {sub && <p className="text-[10px] mt-0.5 text-surface-600">{sub}</p>}
    </div>
  );
}

const NAV_TYPE_LABELS: Record<string, string> = {
  STATISTICAL: "آماری",
  ISSUANCE: "صدور",
  REDEMPTION: "ابطال",
};

export default function FundNavEnginePanel({ symbol }: { symbol: string }) {
  const [navType, setNavType] = useState("STATISTICAL");
  const { data, isLoading, isError } = useFundNavDashboard(symbol);
  const calc = useCalculateFundNav(symbol);
  const recon = useReconcileFundNav(symbol);
  const updateBreak = useUpdateNavBreak(symbol);
  const classNav = useFundClassNav(symbol);
  const calcClass = useCalculateClassNav(symbol);

  async function handleCalculate() {
    try {
      const run = await calc.mutateAsync(navType);
      toast.success(run ? `NAV مستقل ثبت شد (اجرا #${run.run_id})` : "اجرای NAV انجام شد");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در محاسبه NAV");
    }
  }

  async function handleReconcile() {
    try {
      const result = await recon.mutateAsync(navType);
      if (result?.diff_status === "BREACH") {
        toast.error("مغایرت بااهمیت ثبت شد — پرونده باز شد");
      } else if (result?.diff_status === "WARNING") {
        toast.warning("اختلاف در محدوده هشدار است");
      } else {
        toast.success("تطبیق انجام شد");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در تطبیق");
    }
  }

  async function handleBreak(breakId: number, lifecycle: string) {
    try {
      await updateBreak.mutateAsync({ breakId, lifecycle });
      toast.success("وضعیت پرونده مغایرت به‌روزرسانی شد");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در به‌روزرسانی پرونده");
    }
  }

  async function handleClassCalc() {
    try {
      const result = await calcClass.mutateAsync();
      if (result) {
        toast.success("تخصیص NAV طبقاتی محاسبه و ذخیره شد");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در محاسبه NAV طبقاتی");
    }
  }

  const latest = data?.latest_run ?? null;
  const rec = data?.latest_reconciliation ?? null;
  const breaks = data?.open_breaks ?? [];
  const busy = calc.isPending || recon.isPending;

  return (
    <Card
      title="محاسبه NAV مستقل و تطبیق با مرجع"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={navType}
            onChange={(e) => setNavType(e.target.value)}
            className="text-[10px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-surface-300"
          >
            {Object.entries(NAV_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                NAV {label}
              </option>
            ))}
          </select>
          <button
            onClick={handleCalculate}
            disabled={busy}
            className="text-[10px] font-bold text-primary-300 hover:text-primary-200 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg px-3 py-1.5 transition-all disabled:opacity-50"
          >
            {calc.isPending ? "در حال محاسبه..." : "محاسبه NAV مستقل"}
          </button>
          <button
            onClick={handleReconcile}
            disabled={busy}
            className="text-[10px] font-bold text-accent-amber hover:text-accent-amber bg-accent-amber/10 hover:bg-accent-amber/20 border border-accent-amber/30 rounded-lg px-3 py-1.5 transition-all disabled:opacity-50"
          >
            {recon.isPending ? "در حال تطبیق..." : "تطبیق با مرجع"}
          </button>
        </div>
      }
    >
      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      )}

      {isError && !isLoading && (
        <p className="text-xs text-accent-rose py-4 text-center">
          خطا در دریافت وضعیت NAV مستقل
        </p>
      )}

      {!isLoading && !isError && !latest && (
        <div className="text-center py-8 text-surface-500">
          <p className="text-2xl mb-2">🧮</p>
          <p className="text-xs">
            هنوز اجرای NAV مستقلی برای این صندوق ثبت نشده است.
          </p>
          <p className="text-[10px] text-surface-600 mt-1">
            با «محاسبه NAV مستقل» از موقعیت‌ها، قیمت‌ها و تعداد واحدها محاسبه و نسخه‌دار می‌شود.
          </p>
        </div>
      )}

      {!isLoading && latest && (
        <>
          {/* بُعدهای تطبیق */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Chip
              label={`کیفیت: ${labelOf(QUALITY_LABELS, latest.quality_status)}`}
              tone={qualityTone(latest.quality_status)}
            />
            {rec ? (
              <>
                <Chip
                  label={`مقایسه‌پذیری: ${labelOf(COMPARABILITY_LABELS, rec.comparability_status)}`}
                  tone={rec.comparability_status === "COMPARABLE" ? "pos" : "warn"}
                />
                <Chip
                  label={`مرجع: ${labelOf(REFERENCE_LABELS, rec.reference_status)}`}
                  tone={referenceTone(rec.reference_status)}
                />
                {rec.diff_status && (
                  <Chip
                    label={`اختلاف: ${labelOf(DIFF_LABELS, rec.diff_status)}`}
                    tone={diffTone(rec.diff_status)}
                  />
                )}
              </>
            ) : (
              <Chip label="تطبیق انجام نشده" tone="default" />
            )}
            <span className="text-[10px] text-surface-600">
              {latest.valuation_date} — {NAV_TYPE_LABELS[latest.nav_type] ?? latest.nav_type}
              {latest.mode ? ` — ${latest.mode}` : ""}
            </span>
          </div>

          {/* آمار کلیدی */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <Stat
              label="NAV مستقل هر واحد"
              value={formatNav(latest.nav_per_unit)}
              tone="pos"
              sub={`اجرا #${latest.run_id}`}
            />
            <Stat
              label="NAV مرجع"
              value={rec ? formatNav(rec.reference_nav) : "—"}
              tone={rec?.reference_status === "VALID" ? "default" : "warn"}
              sub={rec ? labelOf(REFERENCE_LABELS, rec.reference_status) : "تطبیق نشده"}
            />
            <Stat
              label="اختلاف (bps)"
              value={formatBps(rec?.bps_diff ?? null)}
              tone={diffTone(rec?.diff_status)}
              sub={rec?.abs_diff != null ? formatNav(rec.abs_diff) + " ریال" : undefined}
            />
            <Stat
              label="پوشش قیمت"
              value={latest.coverage_pct != null ? `${latest.coverage_pct.toFixed(1)}%` : "—"}
              tone={qualityTone(latest.quality_status)}
              sub={`خالص دارایی: ${formatNav(latest.net_assets)}`}
            />
            <Stat label="تعداد واحد" value={formatNav(latest.units_outstanding)} />
            <Stat label="تعداد موقعیت" value={String(latest.positions_count ?? latest.positions?.length ?? 0)} />
            <Stat
              label="دوره پرتفوی"
              value={latest.holdings_period ?? "—"}
              sub="مبنای ریز دارایی"
            />
            <Stat
              label="نسخه موتور"
              value={latest.engine_version ?? "—"}
              sub={latest.policy_version ?? undefined}
            />
          </div>

          {/* NAV طبقاتی (اهرمی/تضمین) */}
          <div className="mb-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <p className="text-[11px] text-surface-400">
                NAV طبقاتی
                {classNav.data?.allocation_type ? ` — ${classNav.data.allocation_type}` : ""}
              </p>
              <button
                onClick={handleClassCalc}
                disabled={calcClass.isPending}
                className="text-[10px] font-bold text-primary-300 hover:text-primary-200 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg px-2 py-1 transition-all disabled:opacity-50"
              >
                {calcClass.isPending ? "در حال محاسبه..." : "محاسبه تخصیص طبقات"}
              </button>
            </div>
            {(classNav.data?.classes?.length ?? 0) > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {(classNav.data?.classes ?? []).map((c) => (
                  <Stat
                    key={c.class_code}
                    label={c.class_code}
                    value={formatNav(c.nav_per_unit)}
                    sub={`خالص: ${formatNav(c.net_assets)} | واحد: ${formatNav(c.units)}`}
                    tone={(c.transfer_amount ?? 0) > 0 ? "pos" : (c.transfer_amount ?? 0) < 0 ? "warn" : "default"}
                  />
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-surface-600">
                پیکربندی طبقات ثبت نشده یا تخصیصی محاسبه نشده است (برای صندوق‌های اهرمی/تضمین).
              </p>
            )}
          </div>

          {/* ردیف‌های ارزش‌گذاری */}
          {(latest.positions?.length ?? 0) > 0 && (
            <div className="mb-4">
              <p className="text-[11px] text-surface-400 mb-2">ریز ارزش‌گذاری (۱۰ ردیف اول)</p>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="text-right py-1.5 px-2 font-normal">نماد</th>
                      <th className="text-right py-1.5 px-2 font-normal">نوع</th>
                      <th className="text-right py-1.5 px-2 font-normal">تعداد</th>
                      <th className="text-right py-1.5 px-2 font-normal">قیمت</th>
                      <th className="text-right py-1.5 px-2 font-normal">منبع</th>
                      <th className="text-right py-1.5 px-2 font-normal">ارزش</th>
                      <th className="text-right py-1.5 px-2 font-normal">کیفیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(latest.positions ?? []).slice(0, 10).map((p, idx) => (
                      <tr key={`${p.instrument_symbol ?? "pos"}-${idx}`} className="border-b border-surface-800/50">
                        <td className="py-1.5 px-2 text-surface-200">
                          {p.instrument_symbol ?? p.instrument_name ?? "—"}
                        </td>
                        <td className="py-1.5 px-2 text-surface-500">{p.holding_type}</td>
                        <td className="py-1.5 px-2 font-mono text-surface-300" dir="ltr">
                          {formatNav(p.quantity)}
                        </td>
                        <td className="py-1.5 px-2 font-mono text-surface-300" dir="ltr">
                          {formatNav(p.price)}
                        </td>
                        <td className="py-1.5 px-2 text-surface-500">{p.price_source ?? "—"}</td>
                        <td className="py-1.5 px-2 font-mono text-surface-200" dir="ltr">
                          {formatNav(p.value)}
                        </td>
                        <td className="py-1.5 px-2">
                          <Chip
                            label={p.quality ?? "—"}
                            tone={p.quality === "LIVE" ? "pos" : p.quality === "MISSING" ? "neg" : "warn"}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* پرونده‌های مغایرت باز */}
          {breaks.length > 0 && (
            <div>
              <p className="text-[11px] text-surface-400 mb-2">
                پرونده‌های مغایرت باز ({breaks.length})
              </p>
              <div className="space-y-2">
                {breaks.map((b) => (
                  <div
                    key={b.break_id}
                    className="flex flex-wrap items-center justify-between gap-2 bg-surface-800/40 rounded-xl p-3"
                  >
                    <div className="flex items-center gap-2">
                      <Chip label={b.severity} tone={b.severity === "BREACH" ? "neg" : "warn"} />
                      <span className="text-[10px] text-surface-400">
                        پرونده #{b.break_id} — {labelOf(BREAK_LIFECYCLE_LABELS, b.lifecycle)}
                      </span>
                      {b.sla_due_at && (
                        <span className="text-[10px] text-surface-600">مهلت: {b.sla_due_at}</span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleBreak(b.break_id, "INVESTIGATING")}
                        disabled={updateBreak.isPending}
                        className="text-[10px] text-accent-amber bg-accent-amber/10 hover:bg-accent-amber/20 rounded-lg px-2 py-1 disabled:opacity-50"
                      >
                        شروع بررسی
                      </button>
                      <button
                        onClick={() => handleBreak(b.break_id, "RESOLVED")}
                        disabled={updateBreak.isPending}
                        className="text-[10px] text-accent-emerald bg-accent-emerald/10 hover:bg-accent-emerald/20 rounded-lg px-2 py-1 disabled:opacity-50"
                      >
                        رفع شد
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] text-surface-600 mt-4">
            NAV مستقل فقط از موقعیت‌ها/قیمت/واحدهای همین صندوق محاسبه می‌شود؛ تطبیق پس از
            گیت‌های مقایسه‌پذیری انجام می‌شود و اجرا در حالت SHADOW است.
          </p>
        </>
      )}
    </Card>
  );
}
