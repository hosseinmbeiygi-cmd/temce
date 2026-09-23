import { describe, expect, it } from "vitest";
import {
  evidenceCoverage,
  isAnswered,
  isVeto,
  mergeAnswers,
  parseNumber,
  previewStages,
  UNKNOWN,
  type Answer,
  type BankEvidence,
  type BankInput,
  type BankQuestion,
  type BankStage,
  type EvidenceValue,
} from "./pre-buy";

/**
 * The client-side *preview* gate. These assertions are mirrors of
 * `tests/unit/test_pre_buy_engine.py`; if the two disagree, the preview will unlock a
 * stage the server still keeps closed — which is why both are pinned here.
 */

const input = (id: string): BankInput => ({ id, label: id, unit: "", role: id, min: null, max: null });

const question = (over: Partial<BankQuestion> & { code: string; stage: number }): BankQuestion => ({
  text: over.code,
  kind: "yes_no_unknown",
  stopper: false,
  hint: "",
  unit: "",
  noteRequired: false,
  golden: false,
  vetoValues: [],
  options: [],
  inputs: [],
  evidence: [],
  ...over,
});

const stages: BankStage[] = [
  { id: 0, key: "self", title: "خودتان", purpose: "", rule: "" },
  { id: 1, key: "sust", title: "پایهٔ سهم", purpose: "", rule: "" },
  { id: 2, key: "sector", title: "بخش", purpose: "", rule: "" },
];

const questions: BankQuestion[] = [
  question({ code: "A1", stage: 0 }),
  question({ code: "A2", stage: 0, kind: "number", inputs: [input("entry")] }),
  question({ code: "B1", stage: 1, stopper: true, vetoValues: ["no"] }),
  question({ code: "B2", stage: 1, noteRequired: true }),
  question({ code: "C1", stage: 2, stopper: true, options: [{ id: "ok", label: "خوب", veto: false }, { id: "bad", label: "بد", veto: true }] }),
];

const ans = (value: string | null, note: string | null = null, numbers: Record<string, number> = {}): Answer => ({
  value,
  numbers,
  note,
  answeredAt: null,
});

const stageOf = (answers: Record<string, Answer>) => previewStages(stages, questions, answers);

describe("pre-buy preview gate", () => {
  it("keeps every stage but the first locked on a blank sheet", () => {
    const out = stageOf({});
    expect(out[0]).toMatchObject({ locked: false, complete: false, status: "empty" });
    expect(out[1].locked).toBe(true);
    expect(out[2].locked).toBe(true);
  });

  it("opens the next stage only when the previous one is fully answered", () => {
    expect(stageOf({ A1: ans("yes") })[0]).toMatchObject({ complete: false, answered: 1 });
    const filled = stageOf({ A1: ans("yes"), A2: ans(null, null, { entry: 3220 }) });
    expect(filled[0]).toMatchObject({ complete: true, status: "complete" });
    expect(filled[1].locked).toBe(false);
    expect(filled[2].locked).toBe(true);
  });

  it("treats «نمی‌دانم» as an answer that blocks progression", () => {
    const out = stageOf({ A1: ans(UNKNOWN), A2: ans(null, null, { entry: 3220 }) });
    expect(out[0]).toMatchObject({ status: "blocked_unknown", complete: false });
    expect(out[1].locked).toBe(true);
  });

  it("keeps a stage open until a required written justification arrives", () => {
    const answered = stageOf({
      A1: ans("yes"),
      A2: ans(null, null, { entry: 3220 }),
      B1: ans("yes"),
      B2: ans("no"),
    });
    expect(answered[1]).toMatchObject({ complete: false, status: "in_progress" });
    expect(answered[2].locked).toBe(true);

    const justified = stageOf({
      A1: ans("yes"),
      A2: ans(null, null, { entry: 3220 }),
      B1: ans("yes"),
      B2: ans("no", "چون سهم را با حد ضرر می‌خرم"),
    });
    expect(justified[1].complete).toBe(true);
    expect(justified[2].locked).toBe(false);
  });

  it("rejects only on a ★ question's authored veto value", () => {
    const starValue = question({ code: "B1", stage: 1, stopper: true, vetoValues: ["no"] });
    const plain = question({ code: "X", stage: 0 });
    const optionStar = questions[4];

    expect(isVeto(starValue, ans("no"))).toBe(true);
    expect(isVeto(starValue, ans(UNKNOWN))).toBe(false);
    expect(isVeto(plain, ans("no"))).toBe(false);
    expect(isVeto(optionStar, ans("bad"))).toBe(true);
    expect(isVeto(optionStar, ans("ok"))).toBe(false);

    const rejected = stageOf({
      A1: ans("yes"),
      A2: ans(null, null, { entry: 3220 }),
      B1: ans("no"),
      B2: ans("yes", "توضیح"),
    });
    expect(rejected[1]).toMatchObject({ status: "vetoed", complete: true });
    expect(rejected[2].locked).toBe(false);
  });

  it("requires every declared input of a numeric question", () => {
    const two = question({ code: "N", stage: 0, kind: "number", inputs: [input("a"), input("b")] });
    expect(isAnswered(two, ans(null, null, { a: 1 }))).toBe(false);
    expect(isAnswered(two, ans(null, null, { a: 1, b: 2 }))).toBe(true);
  });
});

describe("pre-buy input helpers", () => {
  it("reads figures typed in Persian, Arabic-Indic, or with separators", () => {
    expect(parseNumber("۳۲۲۰")).toBe(3220);
    expect(parseNumber("12,500")).toBe(12500);
    expect(parseNumber("۱۲٫۵")).toBe(12.5);
    expect(parseNumber("−4.5")).toBe(-4.5);
    expect(parseNumber("")) .toBeNull();
    expect(parseNumber("مجهول")).toBeNull();
  });

  it("lets an explicit null delete a stored answer", () => {
    const merged = mergeAnswers({ A1: ans("yes"), A2: ans("no") }, { A2: null, B1: ans("yes") });
    expect(Object.keys(merged).sort()).toEqual(["A1", "B1"]);
  });
});

describe("evidence coverage", () => {
  const ref = (key: string): BankEvidence => ({ key, label: key, source: "GET /x", unit: "" });
  const value = (status: "available" | "missing", declared = false): EvidenceValue => ({
    value: status === "available" ? 1 : null,
    unit: "",
    source: "GET /x",
    label: "l",
    asOf: null,
    status,
    note: declared ? "در پلتفرم ذخیره نمی‌شود" : "برای این نماد یافت نشد",
    declared,
  });

  it("keeps the platform's own gaps apart from the symbol's", () => {
    const coverage = evidenceCoverage(
      [ref("a"), ref("b"), ref("c")],
      { a: value("available"), b: value("missing"), c: value("missing", true) }
    );

    expect(coverage).toMatchObject({ available: 1, total: 3, declared: 1 });
    expect(coverage.missing.map((m) => m.key)).toEqual(["b", "c"]);
  });

  it("counts nothing as declared before the sheet has been resolved", () => {
    expect(evidenceCoverage([ref("a")], null)).toMatchObject({ available: 0, declared: 0 });
  });
});
