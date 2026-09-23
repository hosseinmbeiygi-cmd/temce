"use client";

/**
 * The verdict card — the only place the app states whether a buy is authorised.
 *
 * Everything here is the server's evaluation, never a client-side recomputation: the
 * five golden questions, the arithmetic the engine derived from the answers, and the
 * blocking reasons are what `core/question_bank/engine.py` returned for this sheet.
 */

import { Check, Clock, FileText, Pause, Play, RotateCcw, Send, ShieldAlert, X } from "lucide-react";
import { VERDICT_META, type Evaluation, type SheetStatus } from "@/lib/pre-buy";
import { cn } from "@/lib/cn";
import { Chip, fmt, Panel } from "./ui";

const VERDICT_ICON = {
  check: Check,
  x: X,
  pause: Pause,
  clock: Clock,
  play: Play,
} as const;

export function VerdictPanel({
  evaluation,
  status,
  dirty,
  saving,
  statement,
  onStatement,
  onSubmit,
  onReopen,
  onPrint,
}: {
  evaluation: Evaluation | null;
  status: SheetStatus;
  dirty: boolean;
  saving: boolean;
  statement: string;
  onStatement: (v: string) => void;
  onSubmit: () => void;
  onReopen: () => void;
  onPrint: () => void;
}) {
  const submitted = status === "SUBMITTED";

  if (!evaluation) {
    return (
      <Panel title="قضاوت" desc="هنوز ارزیابی از سرور دریافت نشده است.">
        <div className="h-16" />
      </Panel>
    );
  }

  const meta = VERDICT_META[evaluation.verdict];
  const Icon = VERDICT_ICON[meta.icon];
  const available = evaluation.derived.filter((d) => d.available);
  const unavailable = evaluation.derived.filter((d) => !d.available);

  return (
    <Panel
      title="قضاوت برگه"
      desc="هر پاسخ، شواهد زنده را دوباره می‌خواند و قضاوت از نو محاسبه می‌شود."
      actions={
        <>
          {saving && <Chip label="در حال ذخیره" tone="muted" />}
          {!saving && dirty && <Chip label="تغییر ذخیره‌نشده" tone="warn" />}
        </>
      }
    >
      <div className={cn("rounded-xl border p-3", meta.ring)}>
        <div className="flex items-center gap-2">
          <Icon className={cn("w-5 h-5 shrink-0", meta.className)} />
          <p className={cn("text-sm font-extrabold leading-relaxed", meta.className)}>{evaluation.verdictLabel}</p>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-surface-400">
          <span>
            پاسخ‌ها: <b dir="ltr">{fmt(evaluation.answered)} از {fmt(evaluation.total)}</b>
          </span>
          <span>
            پیشرفت: <b dir="ltr">{fmt(evaluation.completionPct)}٪</b>
          </span>
          <span>
            مرحلهٔ باز: <b dir="ltr">{fmt(evaluation.unlockedStage + 1)} از ۱۱</b>
          </span>
        </div>
      </div>

      {evaluation.vetoes.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {evaluation.vetoes.map((v) => (
            <li key={v.code} className="flex items-start gap-2 rounded-lg bg-accent-rose/10 p-2">
              <ShieldAlert className="mt-0.5 w-3.5 h-3.5 shrink-0 text-accent-rose" />
              <span className="text-[11px] leading-relaxed text-surface-200">
                <b className="text-accent-rose">{v.answer}</b> به {v.code}: {v.text}
              </span>
            </li>
          ))}
        </ul>
      )}

      {evaluation.blockingReasons.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[11px] font-bold text-surface-300">چه چیزی جلوی تأیید را گرفته است</h4>
          <ul className="mt-1 space-y-1">
            {evaluation.blockingReasons.map((r) => (
              <li key={r} className="flex gap-1.5 text-[11px] leading-relaxed text-surface-400">
                <span className="text-accent-amber">•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {evaluation.golden.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[11px] font-bold text-surface-300">سؤالات طلایی این بانک</h4>
          <ul className="mt-1 space-y-1">
            {evaluation.golden.map((g) => (
              <li key={g.code} className="flex items-start justify-between gap-2 text-[11px] leading-relaxed">
                <span className="text-surface-400">{g.text}</span>
                <Chip
                  label={g.blocking ? "بی‌پاسخ / نمی‌دانم" : g.answer}
                  tone={g.blocking ? "warn" : "pos"}
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      {available.length > 0 && (
        <div className="mt-3">
          <h4 className="text-[11px] font-bold text-surface-300">محاسبه‌های برگه</h4>
          <div className="mt-1 grid gap-1.5 sm:grid-cols-2">
            {available.map((d) => (
              <div key={d.key} className="rounded-lg bg-surface-800/60 p-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[10px] text-surface-500">{d.label}</span>
                  <span className="text-[12px] font-bold text-surface-100" dir="ltr">
                    {fmt(d.value, decimalsFor(d.value))}
                    {d.unit && <span className="text-[9px] text-surface-500"> {d.unit}</span>}
                  </span>
                </div>
                {d.formula && (
                  <p className="mt-0.5 text-[9px] text-surface-600" dir="ltr">
                    {d.formula}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {unavailable.length > 0 && (
        <p className="mt-2 text-[10px] leading-relaxed text-surface-600">
          محاسبهٔ {unavailable.map((d) => d.label).join("، ")} ممکن نشد:{" "}
          {unavailable[0].note || "ورودی کافی ثبت نشده"}
        </p>
      )}

      <div className="mt-4 border-t border-surface-700/70 pt-3">
        {submitted ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10.5px] leading-relaxed text-surface-500">
              این برگه بایگانی شد؛ پاسخ‌ها و شواهدش قفل هستند و در تاریخچهٔ تصمیم‌ها ثبت شده‌اند.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onPrint}
                className="inline-flex items-center gap-1 rounded-lg border border-surface-700 px-2.5 py-1.5 text-[11px] text-surface-300 hover:bg-surface-800"
              >
                <FileText className="w-3.5 h-3.5" /> چاپ
              </button>
              <button
                type="button"
                onClick={onReopen}
                className="inline-flex items-center gap-1 rounded-lg border border-accent-amber/50 px-2.5 py-1.5 text-[11px] text-accent-amber hover:bg-accent-amber/10"
              >
                <RotateCcw className="w-3.5 h-3.5" /> دوباره باز کن
              </button>
            </div>
          </div>
        ) : (
          <>
            <label className="block">
              <span className="text-[10px] text-surface-400">دلیل خرید در دو جمله (در بایگانی ثبت می‌شود)</span>
              <textarea
                rows={2}
                value={statement}
                onChange={(e) => onStatement(e.target.value)}
                placeholder="اگر نتوانید این دو جمله را بنویسید، برگه را ثبت نکنید."
                className="mt-1 w-full rounded-lg border border-surface-700 bg-surface-900/60 p-2 text-[11.5px] leading-relaxed text-surface-100 outline-none focus:border-primary-500"
              />
            </label>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onSubmit}
                disabled={dirty || saving}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-[11.5px] font-bold text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" /> ثبت و بایگانی تصمیم
              </button>
              <button
                type="button"
                onClick={onPrint}
                className="inline-flex items-center gap-1.5 rounded-lg border border-surface-700 px-3 py-1.5 text-[11.5px] text-surface-300 hover:bg-surface-800"
              >
                <FileText className="w-3.5 h-3.5" /> پیش‌نمایش چاپ
              </button>
              {dirty && <span className="text-[10px] text-accent-amber">ابتدا تغییرها ذخیره شود.</span>}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

const decimalsFor = (v: number | null) => (v !== null && Math.abs(v) < 1000 ? 2 : 0);
