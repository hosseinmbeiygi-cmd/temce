/**
 * Pre-buy decision sheet — client contracts and the instant-feedback gate.
 *
 * The source of truth is `core/question_bank` on the backend; the shapes below mirror
 * `services/pre_buy_service.question_to_dict` / `evaluation_to_json` field for field.
 *
 * This module deliberately holds only the *preview* half of the engine: what stage is
 * unlocked, whether the click just made is a ★ rejection, and how complete a stage is.
 * Those drive the UI between keystrokes. The verdict itself is never computed here —
 * `PUT /answers` returns the server's evaluation, and that is the only verdict the app
 * displays, so no client-side bug (or edited bundle) can talk the user into a buy.
 */

export const UNKNOWN = "unknown";

export type AnswerKind = "yes_no_unknown" | "choice" | "number" | "text";
export type Verdict = "not_started" | "in_progress" | "blocked_unknown" | "hold" | "vetoed" | "cleared";
export type StageStatus = "empty" | "in_progress" | "blocked_unknown" | "vetoed" | "complete";
export type SheetStatus = "DRAFT" | "SUBMITTED" | "ABANDONED";

/**
 * What a sheet can be about. Mirrors `core.question_bank.schema.InstrumentType`; the
 * Persian labels come from `GET /instruments`, never from a client-side table, so a type
 * the backend renames cannot keep an outdated name on screen.
 */
export type InstrumentType =
  | "equity"
  | "etf"
  | "fund"
  | "leveraged_fund"
  | "fixed_income"
  | "commodity_fund"
  | "commodity_certificate"
  | "future"
  | "option"
  | "portfolio_allocation"
  | "unknown";

export interface InstrumentChoice {
  key: InstrumentType;
  label: string;
  /** False means the platform recognises the class but has no questions for it yet. */
  hasBank: boolean;
  /** Why there is no bank — a missing column or unwritten questions, never a blank refusal. */
  missingBecause: string;
}

export interface Classification {
  symbol: string;
  instrument_type: InstrumentType;
  label: string;
  /** The table and column that decided it — shown verbatim, because a guess must be visible. */
  basis: string;
  evidenced: boolean;
  hasBank: boolean;
  authoredTypes: InstrumentType[];
  message: string | null;
}

export interface BankOption {
  id: string;
  label: string;
  veto: boolean;
}

export interface BankInput {
  id: string;
  label: string;
  unit: string;
  role: string;
  min: number | null;
  max: number | null;
}

export interface BankEvidence {
  key: string;
  label: string;
  source: string;
  unit: string;
}

export interface BankQuestion {
  code: string;
  stage: number;
  text: string;
  kind: AnswerKind;
  stopper: boolean;
  hint: string;
  unit: string;
  noteRequired: boolean;
  golden: boolean;
  vetoValues: string[];
  options: BankOption[];
  inputs: BankInput[];
  evidence: BankEvidence[];
}

export interface BankStage {
  id: number;
  key: string;
  title: string;
  purpose: string;
  rule: string;
}

export interface Catalogue {
  bankVersion: string;
  instrument: InstrumentType;
  instrumentLabel: string;
  stages: BankStage[];
  questions: BankQuestion[];
  goldenCodes: string[];
  stopperCodes: string[];
  total: number;
}

export interface Answer {
  value: string | null;
  numbers: Record<string, number>;
  note: string | null;
  answeredAt: string | null;
}

export interface EvidenceValue {
  value: number | string | null;
  unit: string;
  source: string;
  label: string;
  asOf: string | null;
  status: "available" | "missing";
  note: string;
  /** True when no column anywhere in the platform holds this figure — the app's gap, not the user's. */
  declared: boolean;
}

export interface StageResult {
  id: number;
  key: string;
  title: string;
  rule: string;
  total: number;
  answered: number;
  complete: boolean;
  locked: boolean;
  status: StageStatus;
  progressPct: number;
  missing: string[];
  unknowns: string[];
  vetoed: string[];
  missingNotes: string[];
}

export interface Veto {
  code: string;
  text: string;
  answer: string;
}

export interface GoldenResult {
  code: string;
  text: string;
  answered: boolean;
  blocking: boolean;
  answer: string;
}

export interface DerivedValue {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  formula: string;
  available: boolean;
  note: string;
}

export interface Evaluation {
  verdict: Verdict;
  verdictLabel: string;
  canBuy: boolean;
  completionPct: number;
  answered: number;
  total: number;
  unlockedStage: number;
  vetoes: Veto[];
  unknowns: string[];
  stopperGaps: string[];
  missingNotes: string[];
  weakEvidence: string[];
  blockingReasons: string[];
  golden: GoldenResult[];
  derived: DerivedValue[];
  stages: StageResult[];
}

export interface Sheet {
  id: number;
  symbol: string;
  instrument_name: string | null;
  instrument_type: InstrumentType;
  /** Which table said so, or «انتخاب کاربر». Rendered in the sheet header. */
  instrument_basis: string | null;
  status: SheetStatus;
  bank_version: string;
  verdict: Verdict;
  completion_pct: number;
  input_hash: string | null;
  answers: Record<string, Answer> | null;
  evidence: Record<string, EvidenceValue> | null;
  detail: Evaluation | null;
  updated_at: string | null;
  submitted_at: string | null;
  next_review_at: string | null;
  /** Only present on the create response. */
  created?: boolean;
}

export interface ReviewRow {
  id: number;
  symbol: string;
  instrument_type: InstrumentType;
  verdict: Verdict;
  completion_pct: number;
  input_hash: string | null;
  bank_version: string;
  statement: string | null;
  created_at: string | null;
}

export const emptyAnswer = (): Answer => ({ value: null, numbers: {}, note: null, answeredAt: null });

export const YES_NO: BankOption[] = [
  { id: "yes", label: "بله", veto: false },
  { id: "no", label: "خیر", veto: false },
  { id: UNKNOWN, label: "نمی‌دانم", veto: false },
];

/** The choices a question actually renders: its own options, or the yes/no/unknown trio. */
export const optionsOf = (q: BankQuestion): BankOption[] =>
  q.kind === "yes_no_unknown" ? YES_NO : q.options;

export function isAnswered(q: BankQuestion, a: Answer | undefined): boolean {
  if (!a) return false;
  if (q.kind === "number")
    return q.inputs.length > 0 && q.inputs.every((i) => a.numbers?.[i.id] !== undefined && a.numbers[i.id] !== null);
  return a.value !== null && a.value !== undefined && a.value !== "";
}

/** A «نمی‌دانم» answer blocks its stage without rejecting the sheet. */
export const isUnknown = (a: Answer | undefined): boolean => a?.value === UNKNOWN;

/** Mirrors `engine._is_veto`: only ★ questions reject, and only on an authored veto value. */
export function isVeto(q: BankQuestion, a: Answer | undefined): boolean {
  if (!q.stopper || !a?.value || a.value === UNKNOWN) return false;
  return q.vetoValues.includes(a.value) || q.options.some((o) => o.veto && o.id === a.value);
}

export function answerLabel(q: BankQuestion, a: Answer | undefined): string {
  if (!a || a.value === null || a.value === undefined || a.value === "") return "—";
  if (a.value === UNKNOWN) return "نمی‌دانم";
  return optionsOf(q).find((o) => o.id === a.value)?.label ?? a.value;
}

/**
 * Parse a figure the user typed.
 *
 * Persian and Arabic-Indic digits, the thousands separators people copy out of a
 * report, and a trailing unit all have to survive the trip — a sheet that silently
 * turns «۱۲,۵۰۰» into zero would size a position wrong.
 */
export function parseNumber(raw: string | number | null | undefined): number | null {
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : null;
  if (!raw) return null;
  const latin = String(raw)
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[٬،]/g, "")
    .replace(/٫/g, ".")
    .replace(/−/g, "-")
    .replace(/[^\d.\-+]/g, "");
  const n = Number(latin);
  return latin !== "" && Number.isFinite(n) ? n : null;
}

/** Server answers with the unsaved draft layered on; an explicit `null` removes one. */
export function mergeAnswers(
  stored: Record<string, Answer> | null | undefined,
  draft: Record<string, Answer | null>
): Record<string, Answer> {
  const out: Record<string, Answer> = { ...(stored ?? {}) };
  for (const [code, value] of Object.entries(draft)) {
    if (value === null) delete out[code];
    else out[code] = value;
  }
  return out;
}

export interface StagePreview {
  id: number;
  total: number;
  answered: number;
  complete: boolean;
  locked: boolean;
  status: StageStatus;
  progressPct: number;
}

/**
 * The same progression rule the engine uses: a stage opens only when every earlier
 * stage is complete, and a «نمی‌دانم» — or an answer whose written justification is
 * still empty — keeps its stage incomplete.
 */
export function previewStages(
  stages: BankStage[],
  questions: BankQuestion[],
  answers: Record<string, Answer>
): StagePreview[] {
  const byStage = new Map<number, BankQuestion[]>();
  for (const q of questions) {
    const list = byStage.get(q.stage) ?? [];
    list.push(q);
    byStage.set(q.stage, list);
  }

  const results: StagePreview[] = [];
  for (const stage of stages) {
    const items = byStage.get(stage.id) ?? [];
    const answered = items.filter((q) => isAnswered(q, answers[q.code])).length;
    const vetoed = items.some((q) => isVeto(q, answers[q.code]));
    const unknowns = items.some((q) => isUnknown(answers[q.code]));
    const noteGaps = items.some((q) => {
      const a = answers[q.code];
      if (!a || q.kind === "text" || !q.noteRequired || isUnknown(a)) return false;
      return isAnswered(q, a) && !(a.note ?? "").trim();
    });
    const complete = items.length > 0 && answered === items.length && !unknowns && !noteGaps;
    const locked = stage.id > 0 && !results.every((r) => r.complete);
    const status: StageStatus = vetoed
      ? "vetoed"
      : unknowns
        ? "blocked_unknown"
        : complete
          ? "complete"
          : answered > 0
            ? "in_progress"
            : "empty";
    results.push({
      id: stage.id,
      total: items.length,
      answered,
      complete,
      locked,
      status,
      progressPct: items.length ? Math.round((answered / items.length) * 100) : 0,
    });
  }
  return results;
}

export const STAGE_STATUS_META: Record<StageStatus, { label: string; className: string; dot: string }> = {
  empty: { label: "بی‌پاسخ", className: "text-surface-500", dot: "bg-surface-600" },
  in_progress: { label: "در حال پاسخ", className: "text-primary-300", dot: "bg-primary-400" },
  blocked_unknown: { label: "معلق (نمی‌دانم)", className: "text-accent-amber", dot: "bg-accent-amber" },
  vetoed: { label: "رد شده", className: "text-accent-rose", dot: "bg-accent-rose" },
  complete: { label: "تکمیل", className: "text-accent-emerald", dot: "bg-accent-emerald" },
};

export const VERDICT_META: Record<Verdict, { className: string; ring: string; icon: "check" | "x" | "pause" | "clock" | "play" }> = {
  not_started: { className: "text-surface-400", ring: "border-surface-700 bg-surface-800/50", icon: "play" },
  in_progress: { className: "text-primary-300", ring: "border-primary-500/40 bg-primary-600/10", icon: "clock" },
  blocked_unknown: { className: "text-accent-amber", ring: "border-accent-amber/40 bg-accent-amber/10", icon: "pause" },
  hold: { className: "text-accent-amber", ring: "border-accent-amber/40 bg-accent-amber/10", icon: "pause" },
  vetoed: { className: "text-accent-rose", ring: "border-accent-rose/50 bg-accent-rose/10", icon: "x" },
  cleared: { className: "text-accent-emerald", ring: "border-accent-emerald/50 bg-accent-emerald/10", icon: "check" },
};

/** Every distinct evidence handle the bank asks for, in first-mention order. */
export function evidenceRefs(questions: BankQuestion[]): BankEvidence[] {
  const seen = new Map<string, BankEvidence>();
  for (const q of questions) for (const e of q.evidence) if (!seen.has(e.key)) seen.set(e.key, e);
  return [...seen.values()];
}

/**
 * How much of the evidence the platform can actually answer today.
 *
 * Reported rather than hidden: a sheet that reads «۱۲ از ۴۷ شاهد» is telling the user
 * where the analysis is thin, which is the whole point of an honest decision sheet.
 */
export function evidenceCoverage(
  refs: BankEvidence[],
  resolved: Record<string, EvidenceValue> | null | undefined
): { available: number; total: number; declared: number; missing: BankEvidence[] } {
  const missing = refs.filter((r) => resolved?.[r.key]?.status !== "available");
  // A figure the platform can never produce is the app's gap; one it failed to read for this
  // symbol is the user's. Counting them together would blame the user for a missing column.
  const declared = missing.filter((r) => resolved?.[r.key]?.declared).length;
  return { available: refs.length - missing.length, total: refs.length, declared, missing };
}

export const SCHEMA_HINT =
  "پاسخ «نمی‌دانم» مجاز است و مرحلهٔ بعد را باز نمی‌کند. سؤالات ستاره‌ای شرط رد خرید هستند.";
