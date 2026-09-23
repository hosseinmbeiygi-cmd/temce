"use client";

/**
 * One question of the bank: its own text, its answer control, and its evidence.
 *
 * The card renders the ★ warning from the answer it was given rather than from the
 * verdict: the server re-evaluates on save, but the user should see the consequence of
 * a starred rejection on the same click that makes it.
 */

import { useState } from "react";
import { Eraser, ShieldAlert } from "lucide-react";
import {
  answerLabel,
  isVeto,
  optionsOf,
  parseNumber,
  UNKNOWN,
  type Answer,
  type BankQuestion,
  type EvidenceValue,
} from "@/lib/pre-buy";
import { cn } from "@/lib/cn";
import { Chip, toneText } from "./ui";
import { EvidenceStrip } from "./EvidenceStrip";

export interface QuestionCardProps {
  question: BankQuestion;
  answer: Answer | undefined;
  evidence: Record<string, EvidenceValue> | null;
  onChange: (next: Answer | null) => void;
  readOnly?: boolean;
}

const blank = (): Answer => ({ value: null, numbers: {}, note: null, answeredAt: null });

export function QuestionCard({ question, answer, evidence, onChange, readOnly }: QuestionCardProps) {
  const vetoed = isVeto(question, answer);
  const answered = answerLabel(question, answer);

  const patch = (part: Partial<Answer>) => onChange({ ...blank(), ...(answer ?? {}), ...part });

  return (
    <article
      className={cn(
        "rounded-xl border p-3 transition-colors",
        vetoed ? "border-accent-rose/50 bg-accent-rose/5" : "border-surface-700/70 bg-surface-800/30",
        question.golden && !vetoed && "border-primary-500/40 bg-primary-600/5"
      )}
    >
      <header className="flex flex-wrap items-start gap-x-2 gap-y-1">
        <span className="text-[10px] font-mono text-surface-500" dir="ltr">
          {question.code}
        </span>
        {question.stopper && (
          <Chip label="★ شرط رد" tone="neg" title="پاسخ نامناسب به این سؤال تحلیل را رد می‌کند" />
        )}
        {question.golden && <Chip label="سؤال طلایی" tone="accent" />}
        <p className="w-full text-[12.5px] font-bold leading-relaxed text-surface-100">{question.text}</p>
      </header>

      {question.hint && <p className="mt-1 text-[10.5px] leading-relaxed text-surface-500">{question.hint}</p>}

      <div className="mt-2.5">
        {question.kind === "number" ? (
          <NumberFields question={question} answer={answer} onChange={onChange} readOnly={readOnly} />
        ) : question.kind === "text" ? (
          <ProseField answer={answer} onChange={onChange} readOnly={readOnly} />
        ) : (
          <ChoiceField question={question} answer={answer} onChange={onChange} readOnly={readOnly} />
        )}
      </div>

      {question.noteRequired && question.kind !== "text" && (
        <label className="mt-2.5 block">
          <span className="text-[10px] text-accent-amber">توضیح نوشتنی — بدون آن برگه کامل نمی‌شود</span>
          <textarea
            rows={2}
            value={answer?.note ?? ""}
            disabled={readOnly}
            onChange={(e) => patch({ note: e.target.value || null })}
            className="mt-1 w-full rounded-lg border border-surface-700 bg-surface-900/60 p-2 text-[11.5px] leading-relaxed text-surface-100 outline-none focus:border-primary-500 disabled:opacity-60"
            placeholder="چرا؟"
          />
        </label>
      )}

      {vetoed && (
        <p className="mt-2 flex items-center gap-1.5 text-[11px] font-bold text-accent-rose">
          <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
          این پاسخ شرط ستاره‌ای را می‌شکند؛ قضاوت نهایی «نخرید» می‌شود.
        </p>
      )}
      {!vetoed && answer?.value === UNKNOWN && (
        <p className="mt-2 text-[11px] text-accent-amber">
          «نمی‌دانم» ثبت شد. تا این پاسخ روشن نشود، مرحلهٔ بعد باز نمی‌شود.
        </p>
      )}

      <EvidenceStrip items={question.evidence} resolved={evidence} />

      {answered !== "—" && (
        <div className="mt-2 flex items-center justify-between">
          <span className={cn("text-[10px]", toneText(vetoed ? "neg" : "muted"))}>پاسخ فعلی: {answered}</span>
          {!readOnly && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className="inline-flex items-center gap-1 text-[10px] text-surface-500 hover:text-surface-300"
            >
              <Eraser className="w-3 h-3" />
              پاک کردن
            </button>
          )}
        </div>
      )}
    </article>
  );
}

function ChoiceField({
  question,
  answer,
  onChange,
  readOnly,
}: {
  question: BankQuestion;
  answer: Answer | undefined;
  onChange: (next: Answer | null) => void;
  readOnly?: boolean;
}) {
  const options = optionsOf(question);
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label={question.text}>
      {options.map((o) => {
        const active = answer?.value === o.id;
        return (
          <button
            key={o.id}
            type="button"
            disabled={readOnly}
            aria-pressed={active}
            onClick={() => onChange({ ...(answer ?? blank()), value: o.id })}
            className={cn(
              "rounded-lg border px-2.5 py-1.5 text-[11.5px] font-bold transition-colors disabled:opacity-60",
              active
                ? o.veto
                  ? "border-accent-rose/60 bg-accent-rose/15 text-accent-rose"
                  : o.id === UNKNOWN
                    ? "border-accent-amber/60 bg-accent-amber/15 text-accent-amber"
                    : "border-primary-500/60 bg-primary-600/20 text-primary-200"
                : "border-surface-700 bg-surface-800/60 text-surface-300 hover:border-surface-600 hover:text-surface-100"
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function ProseField({
  answer,
  onChange,
  readOnly,
}: {
  answer: Answer | undefined;
  onChange: (next: Answer | null) => void;
  readOnly?: boolean;
}) {
  return (
    <textarea
      rows={3}
      disabled={readOnly}
      value={answer?.value ?? ""}
      onChange={(e) => {
        const text = e.target.value;
        onChange(text.trim() ? { ...(answer ?? blank()), value: text } : null);
      }}
      placeholder="پاسخ خود را بنویسید…"
      className="w-full rounded-lg border border-surface-700 bg-surface-900/60 p-2 text-[11.5px] leading-relaxed text-surface-100 outline-none focus:border-primary-500 disabled:opacity-60"
    />
  );
}

function NumberFields({
  question,
  answer,
  onChange,
  readOnly,
}: {
  question: BankQuestion;
  answer: Answer | undefined;
  onChange: (next: Answer | null) => void;
  readOnly?: boolean;
}) {
  // Raw text is local on purpose: re-seeding it from the stored answer on every render
  // would fight the cursor while a digit is being typed.
  const [raw, setRaw] = useState<Record<string, string>>(() => {
    const seed: Record<string, string> = {};
    for (const inp of question.inputs) {
      const v = answer?.numbers?.[inp.id];
      if (v !== undefined && v !== null) seed[inp.id] = String(v);
    }
    return seed;
  });

  const commit = (id: string, text: string) => {
    const nextRaw = { ...raw, [id]: text };
    setRaw(nextRaw);
    const numbers: Record<string, number> = {};
    for (const inp of question.inputs) {
      const n = parseNumber(nextRaw[inp.id]);
      if (n !== null) numbers[inp.id] = n;
    }
    const hasValue = Object.keys(numbers).length > 0;
    onChange(hasValue ? { ...(answer ?? blank()), numbers } : null);
  };

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {question.inputs.map((inp) => {
        const parsed = parseNumber(raw[inp.id]);
        const outOfRange =
          parsed !== null && ((inp.min !== null && parsed < inp.min) || (inp.max !== null && parsed > inp.max));
        return (
          <label key={inp.id} className="block">
            <span className="block text-[10px] text-surface-400">
              {inp.label}
              {inp.unit && <span className="text-surface-600"> ({inp.unit})</span>}
            </span>
            <input
              type="text"
              inputMode="decimal"
              dir="ltr"
              disabled={readOnly}
              value={raw[inp.id] ?? ""}
              onChange={(e) => commit(inp.id, e.target.value)}
              className={cn(
                "mt-1 w-full rounded-lg border bg-surface-900/60 px-2 py-1.5 text-left font-mono text-[12px] text-surface-100 outline-none disabled:opacity-60",
                outOfRange ? "border-accent-amber/60 focus:border-accent-amber" : "border-surface-700 focus:border-primary-500"
              )}
              placeholder="۰"
            />
            {outOfRange && (
              <span className="mt-0.5 block text-[9px] text-accent-amber">
                خارج از بازهٔ راهنما ({inp.min ?? "−∞"} تا {inp.max ?? "∞"})
              </span>
            )}
          </label>
        );
      })}
    </div>
  );
}
