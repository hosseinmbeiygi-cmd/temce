"use client";

/**
 * The A4 decision sheet.
 *
 * Rendered from `GET /sheets/{id}/export`, which resolves every answer and every
 * evidence figure against the bank — so the printout is the same record the server
 * hashed, not a second reading of the form. It is a decision aid, not a buy
 * instruction: the disclaimer is part of the document.
 */

import { answerLabel, UNKNOWN, type BankQuestion } from "@/lib/pre-buy";
import type { ExportPayload, ExportRow } from "@/lib/pre-buy-queries";

const VERDICTS: Record<string, string> = {
  not_started: "شروع نشده",
  in_progress: "در حال تکمیل",
  blocked_unknown: "معلق — «نمی‌دانم» ثبت شده",
  hold: "معلق — شرط ستاره‌ای تکمیل نشده",
  vetoed: "نخرید (رد)",
  cleared: "تحلیل کامل شد — خرید مجاز مشروط به طرح فروش",
};

export function PrintSheet({
  data,
  questionsByCode,
}: {
  data: ExportPayload;
  questionsByCode: Map<string, BankQuestion>;
}) {
  const stages = [...new Set(data.rows.map((r) => r.stage))].sort((a, b) => a - b);

  return (
    <article className="mx-auto w-full max-w-[210mm] bg-white p-[10mm] text-[10pt] leading-relaxed text-black">
      <header className="mb-3 border-b-2 border-black pb-2">
        <h1 className="text-[15pt] font-black">برگهٔ تصمیم پیش از خرید — {data.symbol}</h1>
        <p className="text-[9pt]">{data.instrument_name ?? "—"}</p>
        <p className="text-[8.5pt]">
          نوع ابزار: <b>{data.instrument_label}</b>
          {data.instrument_basis ? ` — ${data.instrument_basis}` : ""}
        </p>
        <div className="mt-1 flex flex-wrap justify-between gap-2 text-[8.5pt]">
          <span>
            قضاوت: <b>{VERDICTS[data.verdict] ?? data.verdict}</b>
          </span>
          <span>نسخهٔ بانک: {data.bank_version}</span>
          <span>
            پیشرفت: {data.detail?.completionPct ?? 0}٪ — {data.detail?.answered ?? 0} از {data.detail?.total ?? 0}
          </span>
          <span>ثبت: {data.submitted_at ? new Date(data.submitted_at).toLocaleString("fa-IR") : "—"}</span>
        </div>
      </header>

      {data.orphanAnswerCodes.length > 0 && (
        <p className="mb-3 border border-black p-1.5 text-[8.5pt]">
          {data.orphanAnswerCodes.length} پاسخ در این برگه هست که به بانک «{data.instrument_label}» تعلق
          ندارد ({data.orphanAnswerCodes.slice(0, 6).join("، ")}
          {data.orphanAnswerCodes.length > 6 ? "…" : ""}) — نوع ابزار عوض شده و این‌ها در قضاوت شمرده
          نمی‌شوند.
        </p>
      )}

      {data.detail && data.detail.golden.length > 0 && (
        <section className="mb-3">
          <h2 className="mb-1 text-[10.5pt] font-black">پنج سؤال طلایی</h2>
          <ul className="list-inside list-disc space-y-0.5 text-[9pt]">
            {data.detail.golden.map((g) => (
              <li key={g.code}>
                {g.text}: <b>{g.answer || "بی‌پاسخ"}</b>
                {g.blocking && " ← پاسخ نداده‌اید؛ طبق چارچوب نخرید."}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.detail && data.detail.derived.some((d) => d.available) && (
        <section className="mb-3">
          <h2 className="mb-1 text-[10.5pt] font-black">محاسبه‌های برگه</h2>
          <table className="w-full border-collapse text-[8.5pt]">
            <tbody>
              {data.detail.derived
                .filter((d) => d.available)
                .map((d) => (
                  <tr key={d.key} className="border-b border-neutral-300">
                    <td className="py-0.5 pl-2">{d.label}</td>
                    <td className="py-0.5 font-mono font-bold" dir="ltr">
                      {d.value}
                      {d.unit ? ` ${d.unit}` : ""}
                    </td>
                    <td className="py-0.5 text-[7.5pt] text-neutral-600" dir="ltr">
                      {d.formula}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}

      {stages.map((stage) => (
        <section key={stage} className="mb-2 break-inside-avoid">
          <h2 className="border-b border-black text-[10.5pt] font-black">
            مرحلهٔ {stage} — {data.detail?.stages.find((s) => s.id === stage)?.title ?? ""}
          </h2>
          <table className="w-full border-collapse">
            <tbody>
              {data.rows
                .filter((r) => r.stage === stage)
                .map((row) => (
                  <PrintRow key={row.code} row={row} question={questionsByCode.get(row.code)} />
                ))}
            </tbody>
          </table>
        </section>
      ))}

      <footer className="mt-4 border-t-2 border-black pt-2 text-[7.5pt] leading-snug">
        <p className="font-bold">
          این برگه تصمیم شخصی است و توصیهٔ خرید یا فروش نیست. «خرید مجاز» تنها به معناست که چارچوب کامل
          پاسخ شده است — نه اینکه سهم بالا می‌رود.
        </p>
        <p className="mt-0.5 font-mono" dir="ltr">
          hash: {data.input_hash ?? "—"}
        </p>
      </footer>
    </article>
  );
}

function PrintRow({ row, question }: { row: ExportRow; question: BankQuestion | undefined }) {
  const answer = question ? answerLabel(question, { value: row.answer, numbers: row.numbers, note: row.note, answeredAt: null }) : "—";
  const numbers = Object.entries(row.numbers ?? {});
  const unknown = row.answer === UNKNOWN;

  return (
    <tr className="border-b border-neutral-300 align-top">
      <td className="w-[52px] py-1 pl-1 font-mono text-[7.5pt]" dir="ltr">
        {row.code}
        {row.stopper && <span className="font-bold"> ★</span>}
      </td>
      <td className="py-1 pl-2 text-[8.5pt]">{row.text}</td>
      <td className="w-[150px] py-1 text-[8.5pt]">
        <span className={answer === "—" ? "text-neutral-400" : unknown ? "italic" : "font-bold"}>{answer}</span>
        {numbers.length > 0 && (
          <span className="block font-mono text-[7.5pt]" dir="ltr">
            {numbers.map(([k, v]) => `${k}=${v}`).join("، ")}
          </span>
        )}
        {row.note && <span className="block text-[7.5pt] italic">{row.note}</span>}
        {row.evidence.length > 0 && (
          <span className="mt-0.5 block text-[7pt] text-neutral-700">
            {row.evidence
              .map((e) => (e.status === "available" ? `${e.label}: ${e.value}${e.unit ? ` ${e.unit}` : ""}` : null))
              .filter(Boolean)
              .join(" | ")}
            {/* A missing figure is printed, not dropped: a signed sheet that quietly omits its
                own gaps reads as a complete analysis. */}
            {row.evidence.some((e) => e.status !== "available") && (
              <span className="block text-[6.5pt] italic text-neutral-600">
                بدون داده:{" "}
                {row.evidence
                  .filter((e) => e.status !== "available")
                  .map((e) => `${e.label}${e.declared ? " (در این پلتفرم ذخیره نمی‌شود)" : ""}`)
                  .join(" | ")}
              </span>
            )}
          </span>
        )}
      </td>
    </tr>
  );
}
