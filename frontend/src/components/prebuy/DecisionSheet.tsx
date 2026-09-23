"use client";

/**
 * The decision sheet workspace: rail, gated questions, live evidence, verdict.
 *
 * Ownership of state is split on purpose. Unsaved answers live here (so typing is
 * instant), the verdict lives in the server's evaluation (so the app can only ever
 * display a judgement the gate produced). The two meet in `mergeAnswers`, which feeds
 * the *preview* gate — stage unlocking and ★ colouring — and nothing else.
 */

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Loader2, Lock, Play, RefreshCw } from "lucide-react";
import {
  evidenceCoverage,
  evidenceRefs,
  isAnswered,
  mergeAnswers,
  previewStages,
  UNKNOWN,
  type Answer,
  type BankQuestion,
  type Classification,
  type InstrumentChoice,
  type InstrumentType,
  type Sheet,
} from "@/lib/pre-buy";
import {
  useCatalogue,
  useInstruments,
  useOpenSheet,
  useResolveInstrument,
  useSaveAnswers,
  useSheet,
  useSheets,
  useSubmitSheet,
  useReopenSheet,
  useSymbolEvidence,
} from "@/lib/pre-buy-queries";
import { cn } from "@/lib/cn";
import { Chip, fmt, Panel } from "./ui";
import { StageRail } from "./StageRail";
import { QuestionCard } from "./QuestionCard";
import { VerdictPanel } from "./VerdictPanel";

const AUTOSAVE_MS = 900;

/** One draft per symbol, then the newest sheet — mirrors the DB's partial unique index. */
function pickSheet(rows: Sheet[] | undefined, symbol: string): Sheet | undefined {
  if (!rows) return undefined;
  const mine = rows.filter((r) => r.symbol === symbol);
  return mine.find((r) => r.status === "DRAFT") ?? mine[0];
}

export function DecisionSheet({ symbol }: { symbol: string }) {
  const sheets = useSheets();
  const stored = useMemo(() => pickSheet(sheets.data, symbol), [sheets.data, symbol]);
  // The sheet's own instrument class chooses the bank. Previewing a brand-new symbol uses
  // equity, which is also the only bank that exists — an unauthored type would have been
  // refused before a sheet could be created for it.
  const catalogue = useCatalogue(stored?.instrument_type ?? "equity");
  const openSheet = useOpenSheet();

  const sheetId = stored?.id ?? null;
  const sheetQuery = useSheet(sheetId);
  const sheet = sheetQuery.data ?? stored ?? null;

  const save = useSaveAnswers(sheetId);
  const submit = useSubmitSheet(sheetId);
  const reopen = useReopenSheet(sheetId);

  const [draft, setDraft] = useState<Record<string, Answer | null>>({});
  const [active, setActive] = useState<number | null>(null);
  const [statement, setStatement] = useState("");
  const [saveError, setSaveError] = useState("");

  // Stable identities: the bank is cached, so re-deriving `?? []` on every render would
  // throw away every memo below it on every keystroke.
  const questions = useMemo(() => catalogue.data?.questions ?? [], [catalogue.data]);
  const stages = useMemo(() => catalogue.data?.stages ?? [], [catalogue.data]);
  const effective = useMemo(() => mergeAnswers(sheet?.answers, draft), [sheet?.answers, draft]);
  const previews = useMemo(() => previewStages(stages, questions, effective), [stages, questions, effective]);
  const readOnly = sheet?.status === "SUBMITTED";

  const byStage = useMemo(() => {
    const map = new Map<number, BankQuestion[]>();
    for (const q of questions) {
      const list = map.get(q.stage) ?? [];
      list.push(q);
      map.set(q.stage, list);
    }
    return map;
  }, [questions]);

  const stopperCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const q of questions) if (q.stopper) counts[q.stage] = (counts[q.stage] ?? 0) + 1;
    return counts;
  }, [questions]);

  // A new symbol is a new sheet: never carry unsaved answers across instruments.
  useEffect(() => {
    setDraft({});
    setActive(null);
    setStatement("");
    setSaveError("");
  }, [symbol, sheetId]);

  const firstOpen = previews.find((p) => !p.locked && !p.complete) ?? previews[previews.length - 1];
  const current = active ?? firstOpen?.id ?? 0;

  const mutateSave = save.mutate;
  const dirty = Object.keys(draft).length > 0;

  useEffect(() => {
    if (!dirty || readOnly || !sheetId) return;
    const timer = setTimeout(() => {
      mutateSave(
        { answers: draft },
        {
          onSuccess: () => {
            setDraft({});
            setSaveError("");
          },
          onError: (err) =>
            setSaveError(
              `${err instanceof Error ? err.message : "ذخیره ناموفق"} — تغییرها از دست نرفته‌اند؛ با پاسخ بعدی دوباره ذخیره می‌شود.`
            ),
        }
      );
    }, AUTOSAVE_MS);
    return () => clearTimeout(timer);
  }, [dirty, draft, readOnly, sheetId, mutateSave]);

  const refs = useMemo(() => evidenceRefs(questions), [questions]);
  const coverage = evidenceCoverage(refs, sheet?.evidence);
  const previewEvidence = useSymbolEvidence(sheet ? null : symbol);
  const previewCoverage = evidenceCoverage(refs, previewEvidence.data?.evidence);
  const classification = useResolveInstrument(sheet ? null : symbol);
  const instruments = useInstruments(!sheet);
  const authored = useMemo(() => (instruments.data ?? []).filter((i) => i.hasBank), [instruments.data]);

  const onChange = (code: string, next: Answer | null) =>
    setDraft((prev) => ({ ...prev, [code]: next }));

  if (catalogue.isLoading) {
    return (
      <div className="flex items-center gap-2 p-6 text-[12px] text-surface-400">
        <Loader2 className="w-4 h-4 animate-spin" /> بانک سؤالات بارگذاری می‌شود…
      </div>
    );
  }
  if (catalogue.isError) {
    // A refusal from the server («این بانک نوشته نشده») is not a connectivity failure;
    // saying "could not reach the API" would send the user to debug the wrong thing.
    const reason = catalogue.error instanceof Error ? catalogue.error.message : "";
    return (
      <Panel
        title="بانک سؤالات باز نشد"
        desc={reason || "ارتباط با /api/v1/pre-buy/catalogue برقرار نشد."}
      >
        <button
          type="button"
          onClick={() => void catalogue.refetch()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-surface-700 px-3 py-1.5 text-[11.5px] text-surface-300 hover:bg-surface-800"
        >
          <RefreshCw className="w-3.5 h-3.5" /> تلاش دوباره
        </button>
      </Panel>
    );
  }

  if (!sheet)
    return (
      <SheetIntro
        symbol={symbol}
        coverage={previewCoverage}
        counts={
          catalogue.data
            ? {
                questions: catalogue.data.total,
                stages: catalogue.data.stages.length,
                stoppers: catalogue.data.stopperCodes.length,
              }
            : null
        }
        classification={classification.data ?? null}
        authored={authored}
        gapReason={
          instruments.data?.find((i) => i.key === classification.data?.instrument_type)?.missingBecause ?? ""
        }
        starting={openSheet.isPending}
        error={openSheet.error?.message ?? ""}
        onStart={(instrument) =>
          openSheet.mutate(instrument ? { symbol, instrument } : { symbol })
        }
      />
    );

  const stageQuestions = byStage.get(current) ?? [];
  const stageMeta = stages.find((s) => s.id === current);
  const stagePreview = previews.find((p) => p.id === current);
  const locked = stagePreview?.locked ?? false;
  const missing = stageQuestions.filter((q) => !isAnswered(q, effective[q.code]));
  const unknowns = stageQuestions.filter((q) => effective[q.code]?.value === UNKNOWN);
  const index = stages.findIndex((s) => s.id === current);
  const next = stages[index + 1];
  const prev = stages[index - 1];

  return (
    <div className="grid gap-3 lg:grid-cols-[210px_minmax(0,1fr)_330px]">
      <aside className="lg:sticky lg:top-3 lg:self-start">
        <StageRail
          stages={stages}
          previews={previews}
          stopperCounts={stopperCounts}
          active={current}
          onSelect={setActive}
        />
      </aside>

      <div className="min-w-0 space-y-3">
        <header className="glass-card p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="flex items-center gap-2 text-sm font-extrabold text-surface-100">
                {symbol}
                {sheet.instrument_name && (
                  <span className="truncate text-[11px] font-normal text-surface-500">{sheet.instrument_name}</span>
                )}
              </h2>
              <p className="mt-0.5 text-[10px] text-surface-600">
                نسخهٔ بانک {sheet.bank_version}
                {catalogue.data ? ` — ${catalogue.data.instrumentLabel}` : ""}
                {sheet.instrument_basis ? ` (${sheet.instrument_basis})` : ""} — {fmt(coverage.available)} از{" "}
                {fmt(coverage.total)} شاهد زنده
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {sheet.status === "SUBMITTED" && <Chip label="بایگانی‌شده" tone="muted" />}
              {dirty && <Chip label="ذخیره نشده" tone="warn" />}
              {save.isPending && !dirty && <Chip label="در حال ذخیره" tone="accent" />}
              {save.isError && <Chip label="خطای ذخیره" tone="neg" />}
              {sheet.next_review_at && (
                <Chip label={`بازبینی: ${new Date(sheet.next_review_at).toLocaleDateString("fa-IR")}`} tone="muted" />
              )}
            </div>
          </div>
        </header>

        {stageMeta && (
          <div className="rounded-xl border border-surface-700/70 bg-surface-800/40 p-3">
            <div className="flex items-baseline gap-2">
              <span className="text-[10px] font-mono text-surface-500" dir="ltr">
                مرحله {stageMeta.id}
              </span>
              <h3 className="text-[13px] font-extrabold text-surface-100">{stageMeta.title}</h3>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-surface-400">{stageMeta.purpose}</p>
            {stageMeta.rule && (
              <p className="mt-1.5 border-r-2 border-primary-500/50 pr-2 text-[11px] font-bold leading-relaxed text-primary-200">
                {stageMeta.rule}
              </p>
            )}
          </div>
        )}

        {locked ? (
          <Panel title="این مرحله قفل است" desc="قانون چارچوب: تا مرحلهٔ پیشین کامل نشود، مرحلهٔ بعد باز نمی‌شود.">
            <button
              type="button"
              onClick={() => setActive(firstOpen?.id ?? 0)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-[11.5px] font-bold text-white hover:bg-primary-500"
            >
              <Lock className="w-3.5 h-3.5" /> برو به اولین مرحلهٔ کامل‌نشده
            </button>
          </Panel>
        ) : (
          <div className="space-y-2.5">
            {stageQuestions.map((q) => (
              <QuestionCard
                key={q.code}
                question={q}
                answer={effective[q.code]}
                evidence={sheet.evidence}
                onChange={(next) => onChange(q.code, next)}
                readOnly={readOnly}
              />
            ))}
          </div>
        )}

        {!locked && (missing.length > 0 || unknowns.length > 0) && (
          <p className="flex flex-wrap items-center gap-1.5 text-[10.5px] text-surface-500">
            <AlertTriangle className="w-3 h-3 text-accent-amber" />
            برای باز شدن مرحلهٔ بعد: {missing.length} بی‌پاسخ
            {unknowns.length > 0 && `، ${unknowns.length} «نمی‌دانم`}
          </p>
        )}

        <div className="flex items-center justify-between gap-2 pt-1">
          <button
            type="button"
            disabled={!prev}
            onClick={() => prev && setActive(prev.id)}
            className="inline-flex items-center gap-1 rounded-lg border border-surface-700 px-2.5 py-1.5 text-[11px] text-surface-300 hover:bg-surface-800 disabled:opacity-40"
          >
            <ChevronRight className="w-3.5 h-3.5" /> مرحلهٔ قبل
          </button>
          <span className="text-[10px] text-surface-600">
            {fmt(current + 1)} / {fmt(stages.length)}
          </span>
          <button
            type="button"
            disabled={!next}
            onClick={() => next && setActive(next.id)}
            className={cn(
              "inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[11px] transition-colors disabled:opacity-40",
              stagePreview?.complete
                ? "border-accent-emerald/50 text-accent-emerald hover:bg-accent-emerald/10"
                : "border-surface-700 text-surface-400 hover:bg-surface-800"
            )}
          >
            مرحلهٔ بعد <ChevronLeft className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <aside className="space-y-3 lg:sticky lg:top-3 lg:self-start">
        <VerdictPanel
          evaluation={sheet.detail}
          status={sheet.status}
          dirty={dirty}
          saving={submit.isPending || save.isPending}
          statement={statement}
          onStatement={setStatement}
          onSubmit={() => submit.mutate(statement.trim() || null)}
          onReopen={() => reopen.mutate()}
          onPrint={() => window.open(`/pre-buy/print/${sheet.id}`, "_blank", "noopener")}
        />
        {saveError && <p className="text-[10.5px] leading-relaxed text-accent-rose">{saveError}</p>}
        {submit.isError && <p className="text-[10.5px] text-accent-rose">{submit.error?.message}</p>}
        {reopen.isError && <p className="text-[10.5px] text-accent-rose">{reopen.error?.message}</p>}
      </aside>
    </div>
  );
}

function SheetIntro({
  symbol,
  coverage,
  counts,
  classification,
  authored,
  gapReason,
  starting,
  error,
  onStart,
}: {
  symbol: string;
  coverage: { available: number; total: number; declared: number };
  counts: { questions: number; stages: number; stoppers: number } | null;
  classification: Classification | null;
  authored: InstrumentChoice[];
  gapReason: string;
  starting: boolean;
  error: string;
  onStart: (instrument: InstrumentType | null) => void;
}) {
  // Only used when the platform cannot classify the symbol at all: the user then states
  // what they are buying. A recognised type with no bank gets no override — answering a
  // leveraged fund with share questions would be a fabricated analysis, not a fallback.
  const [chosen, setChosen] = useState<InstrumentType | null>(null);
  const undetermined = classification !== null && !classification.evidenced;
  const unbanked = classification !== null && classification.evidenced && !classification.hasBank;
  const blocked = unbanked || (undetermined && chosen === null);

  return (
    <Panel
      title="برگهٔ تصمیم پیش از خرید"
      desc={
        counts
          ? `${fmt(counts.questions)} سؤال در ${fmt(counts.stages)} مرحله؛ ${fmt(counts.stoppers)} شرط ستاره‌ای که پاسخ نامناسب به هر کدام یعنی نخرید.`
          : "شمار سؤال و مرحله پس از خواندن بانک این نوع ابزار نمایش داده می‌شود."
      }
      className="mx-auto max-w-2xl"
    >
      <ul className="space-y-1.5 text-[11.5px] leading-relaxed text-surface-400">
        <li className="flex gap-2">
          <span className="text-accent-amber">•</span>
          پاسخ «نمی‌دانم» مجاز است، ولی مرحلهٔ بعد را باز نمی‌کند.
        </li>
        <li className="flex gap-2">
          <span className="text-primary-300">•</span>
          پنج سؤال طلایی در آخر: چرا این {classification?.label ?? "ابزار"}، چرا این
          قیمت، چقدر بخرم، کِی بفروشم، و چه چیزی این تحلیل را باطل می‌کند.
        </li>
        <li className="flex gap-2">
          <span className="text-accent-emerald">•</span>
          {fmt(coverage.available)} از {fmt(coverage.total)} شاهد این نماد از دادهٔ زندهٔ پلتفرم خوانده
          می‌شود؛ {fmt(Math.max(coverage.total - coverage.available - coverage.declared, 0))} مورد را باید
          خودتان پاسخ دهید و همین، نقطهٔ ضعف تحلیل شماست.
        </li>
        {coverage.declared > 0 && (
          <li className="flex gap-2">
            <span className="text-accent-rose">•</span>
            {fmt(coverage.declared)} شاهد اصلاً در داده‌های این پلتفرم وجود ندارد — این کمبودِ برنامه است،
            نه کاستی تحلیل شما؛ برای همین با «—» و دلیلش نشان داده می‌شود، نه با عدد حدسی.
          </li>
        )}
        {classification && (
          <li className="flex gap-2">
            <span className={undetermined || unbanked ? "text-accent-rose" : "text-surface-600"}>•</span>
            <span>
              {undetermined
                ? `نوع ابزار «${symbol}» در هیچ جدول برنامه نیست؛ بانک سهام را به آن تحمیل نمی‌کنیم.`
                : `نوع ابزار: ${classification.label} — ${classification.basis}`}
            </span>
          </li>
        )}
        {unbanked && (
          <li className="flex gap-2">
            <span className="text-accent-rose">•</span>
            {gapReason ||
              "بانک سؤالات این نوع هنوز نوشته نشده است، پس برگه‌ای برایش ساخته نمی‌شود."}
          </li>
        )}
      </ul>
      {undetermined && authored.length > 0 && (
        <label className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-surface-400">
          این نماد را چه می‌دانید؟
          <select
            value={chosen ?? ""}
            onChange={(e) => setChosen((e.target.value || null) as InstrumentType | null)}
            className="rounded-lg border border-surface-700 bg-surface-900 px-2 py-1 text-[11.5px] text-surface-200"
          >
            <option value="">— انتخاب کنید —</option>
            {authored.map((i) => (
              <option key={i.key} value={i.key}>
                {i.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onStart(undetermined ? chosen : null)}
          disabled={starting || blocked}
          title={unbanked ? "برای این نوع ابزار سؤال نوشته نشده است" : undefined}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3.5 py-2 text-[12px] font-bold text-white hover:bg-primary-500 disabled:opacity-60"
        >
          {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          شروع برگهٔ {symbol}
        </button>
        <span className="text-[10px] text-surface-600">برگه برای این نماد ساخته می‌شود و قابل حذف نیست؛ می‌توانید رها کنید.</span>
      </div>
      {error && <p className="mt-2 text-[11px] text-accent-rose">{error}</p>}
    </Panel>
  );
}
