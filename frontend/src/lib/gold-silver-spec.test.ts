import { describe, expect, it } from "vitest";
import * as spec from "./gold-silver-spec";
import {
  AssistantRulesError,
  evaluateTrade,
  minimumTargetForFilter,
  feeTerms,
  minutesOfDay,
  parseAssistantRules,
  requiredGrossMovePct,
  requiredGrossMovePctFor,
  roundTripFeePct,
  sessionForWeekday,
  sessionState,
  settlementLabel,
  tehranClock,
  type AssistantRules,
} from "./gold-silver-spec";
import {
  ASSISTANT_RULES_PAYLOAD,
  assistantRulesDraft,
} from "@/__tests__/fixtures/assistant-rules";

const rules: AssistantRules = parseAssistantRules(ASSISTANT_RULES_PAYLOAD);
const filter = rules.signal_filter;

/* ─────────────── §۲۶/§۲۷.۱: عدد در فرانت‌اند هاردکد نیست ─────────────── */

describe("gold-silver-spec — منبع واحد اعداد", () => {
  it("هیچ تعرفه یا آستانهٔ هاردکدی صادر نمی‌کند", () => {
    // اگر روزی کسی FEE_SCHEDULE/VALUE_FILTER را برگرداند، صفحه دوباره درِ دومِ
    // حقیقت می‌شود و می‌تواند از گیت سمت سرور جدا بیفتد.
    const exported = spec as unknown as Record<string, unknown>;
    expect(exported.FEE_SCHEDULE).toBeUndefined();
    expect(exported.VALUE_FILTER).toBeUndefined();
    expect(exported.MARKET_HOURS).toBeUndefined();
    expect(exported.FUND_REQUIRED_GROSS_MOVE_PCT).toBeUndefined();
  });

  it("evaluateTrade آستانه را از filter پاس‌شده می‌خواند، نه از ثابت ماژول", () => {
    // `filter` در تایپ الزامی است؛ اینجا هم اثبات می‌کنیم مقدارش واقعاً اثر دارد.
    const strict = { ...filter, min_net_profit_pct: 3.9 };
    const base = { entry: 100, target: 104, stop: 99, costPct: 0.6, probability: 0.6 };
    expect(evaluateTrade({ ...base, filter }).verdict).toBe("opportunity");
    expect(evaluateTrade({ ...base, filter: strict }).verdict).toBe("reject");
  });
});

/* ─────────────── تحلیل پاسخ API (§۱۳: بدون پیش‌فرض خاموش) ─────────────── */

describe("parseAssistantRules", () => {
  it("پاسخ کامل را به مدل تایپ‌شده تبدیل می‌کند", () => {
    expect(rules.version).toBe("1.0");
    expect(rules.fee_schedule.last_updated).toBe("1405-07-22");
    expect(rules.signal_filter.min_net_profit_pct).toBe(2);
    expect(rules.signal_filter.min_risk_reward).toBe(2);
    expect(rules.market_hours.sat_to_wed.close).toBe("18:00");
    expect(rules.market_hours.settlement_days).toBe(1);
  });

  it("عدد نامعتبر را خطای صریح می‌دهد، نه پیش‌فرض", () => {
    const bad = assistantRulesDraft();
    bad.signal_filter.min_net_profit_pct = "2";
    expect(() => parseAssistantRules(bad)).toThrow(AssistantRulesError);
    expect(() => parseAssistantRules(bad)).toThrow(/min_net_profit_pct/);
  });

  it("آستانهٔ نامثبت را رد می‌کند (§۲۶: سود خالص و RR باید مثبت باشند)", () => {
    const zeroProfit = assistantRulesDraft();
    zeroProfit.signal_filter.min_net_profit_pct = 0;
    expect(() => parseAssistantRules(zeroProfit)).toThrow(/سود خالص|min_net_profit_pct/);

    const zeroRr = assistantRulesDraft();
    zeroRr.signal_filter.min_risk_reward = 0;
    expect(() => parseAssistantRules(zeroRr)).toThrow(/ریسک|min_risk_reward/);
  });

  it("تعرفهٔ ناقص یا بدشکل را رد می‌کند", () => {
    const noInstruments = assistantRulesDraft();
    noInstruments.fee_schedule.instruments = {};
    expect(() => parseAssistantRules(noInstruments)).toThrow(/درست‌کم|instruments/);

    const badFee = assistantRulesDraft();
    badFee.fee_schedule.instruments.commodity_fund.fee_per_side = "0.0012";
    expect(() => parseAssistantRules(badFee)).toThrow(/fee_per_side/);
  });

  it("منشأ ناشناخته و ساعت بدشکل را رد می‌کند", () => {
    const badProvenance = assistantRulesDraft();
    badProvenance.signal_filter.provenance.min_risk_reward = "maybe";
    expect(() => parseAssistantRules(badProvenance)).toThrow(/provenance/);

    const badHours = assistantRulesDraft();
    badHours.market_hours.sat_to_wed.close = "";
    expect(() => parseAssistantRules(badHours)).toThrow(/sat_to_wed.close/);

    const badBands = assistantRulesDraft();
    badBands.market_hours.emergency_band_pcts = ["1"];
    expect(() => parseAssistantRules(badBands)).toThrow(/emergency_band_pcts/);
  });

  it("ورودی غیرشیء (مثلاً data تهی) را رد می‌کند", () => {
    expect(() => parseAssistantRules(undefined)).toThrow(AssistantRulesError);
    expect(() => parseAssistantRules(null)).toThrow(AssistantRulesError);
    expect(() => parseAssistantRules([])).toThrow(AssistantRulesError);
  });
});

/* ─────────────── §۲۷.۱ تعرفه ─────────────── */

describe("تعرفهٔ §۲۷.۱", () => {
  it("صندوق کالایی ۰٫۱۲٪ هر سمت و ۰٫۲۴٪ رفت‌وبرگشت است", () => {
    expect(feeTerms(rules, "commodity_fund")?.fee_per_side).toBeCloseTo(0.0012, 8);
    expect(roundTripFeePct(rules, "commodity_fund")).toBeCloseTo(0.24, 8);
  });

  it("گواهی سکه ۰٫۲۵٪ رفت‌وبرگشت با سقف ۳۰۰ میلیون ریال است", () => {
    expect(roundTripFeePct(rules, "coin_certificate")).toBeCloseTo(0.25, 8);
    expect(feeTerms(rules, "coin_certificate")?.fee_cap_irr).toBe(300_000_000);
    expect(feeTerms(rules, "coin_certificate")?.tax_exempt).toBe(true);
  });

  it("گواهی شمش ۰٫۴۸٪ رفت‌وبرگشت با سقف ۴۵۰ میلیون ریال است", () => {
    expect(roundTripFeePct(rules, "bullion_certificate")).toBeCloseTo(0.48, 8);
    expect(feeTerms(rules, "bullion_certificate")?.fee_cap_irr).toBe(450_000_000);
  });

  it("آتی و اختیار «ناموجود» می‌مانند، نه صفر", () => {
    // صفر یک نرخ جعلی می‌سازد؛ سند صریحاً می‌گوید عدد پیدا نشد (§۲۷.۱).
    expect(feeTerms(rules, "futures")?.fee_per_side).toBeNull();
    expect(feeTerms(rules, "futures")?.provenance).toBe("unavailable");
    expect(roundTripFeePct(rules, "futures")).toBeNull();
    expect(requiredGrossMovePctFor(rules, "futures")).toBeNull();
  });

  it("کارمزد صندوق «فرض» است تا تأیید صورتحساب کارگزار (§۲۸.۲)", () => {
    expect(feeTerms(rules, "commodity_fund")?.provenance).toBe("assumption");
    expect(feeTerms(rules, "commodity_fund")?.label_fa).toBe("صندوق کالایی طلا و نقره");
  });
});

/* ─────────────── §۲۰ حرکت ناخالص لازم ─────────────── */

describe("requiredGrossMovePct (§۲۰)", () => {
  it("هدف ۲٪ با کارمزد ۰٫۲۴٪ رفت‌وبرگشت یعنی حداقل ۲٫۲۴٪ حرکت ناخالص", () => {
    expect(requiredGrossMovePctFor(rules)).toBeCloseTo(2.24, 6);
  });

  it("اسپرد، لغزش و هزینهٔ دیگر به حرکت لازم اضافه می‌شوند", () => {
    const g = requiredGrossMovePct({
      targetNetPct: 2,
      buyFeePct: 0.12,
      sellFeePct: 0.12,
      spreadPct: 0.3,
      slippagePct: 0.1,
      otherPct: 0.05,
    });
    expect(g).toBeCloseTo(2.69, 6);
  });

  it("با آستانهٔ سروشدهٔ متفاوت، حرکت لازم هم عوض می‌شود (بدون عدد هاردکد)", () => {
    const looser: AssistantRules = {
      ...rules,
      signal_filter: { ...filter, min_net_profit_pct: 3 },
    };
    expect(requiredGrossMovePctFor(looser)).toBeCloseTo(3.24, 6);
  });
});

/* ─────────────── §۲۶/§۲۰ فرمول‌ها ─────────────── */

describe("evaluateTrade (§۲۶)", () => {
  // سه نمونهٔ عددی سند §۲۶ — سرمایه ۱۰۰ واحد، ورود ۱۰۰، هزینهٔ کل ۰٫۶٪.
  const caseAlef = { entry: 100, target: 104, stop: 99, costPct: 0.6, filter };
  const caseBe = { entry: 100, target: 103, stop: 98.5, costPct: 0.6, filter };
  const caseJim = { entry: 100, target: 102, stop: 99, costPct: 0.6, filter };

  it("حالت الف: W=۳٫۴٪ و L=۱٫۶٪ و RR=۲٫۱۳ ⇒ با p معتبر سیگنال صادر می‌شود", () => {
    const r = evaluateTrade({ ...caseAlef, probability: 0.6 });
    expect(r.netProfitPct).toBeCloseTo(3.4, 6);
    expect(r.netRiskPct).toBeCloseTo(1.6, 6);
    expect(r.riskReward).toBeCloseTo(2.125, 6);
    expect(r.expectedValuePct).toBeCloseTo(1.4, 6);
    expect(r.verdict).toBe("opportunity");
    expect(r.reasons).toEqual([]);
  });

  it("حالت الف بدون p معتبر ⇒ «پایش» است، نه «بررسی فرصت»", () => {
    const r = evaluateTrade(caseAlef);
    expect(r.verdict).toBe("watch");
    expect(r.expectedValuePct).toBeNull();
    expect(r.reasons.join(" ")).toContain("پایش");
  });

  it("حالت ب: RR=۱٫۱۴ کمتر از ۲ ⇒ رد با دلیل عددی", () => {
    const r = evaluateTrade({ ...caseBe, probability: 0.7 });
    expect(r.riskReward).toBeCloseTo(1.1429, 3);
    expect(r.verdict).toBe("reject");
    expect(r.reasons.join(" ")).toContain("ریسک/ریوارد");
  });

  it("حالت ج: سود خالص ۱٫۴٪ کمتر از ۲٪ ⇒ رد", () => {
    const r = evaluateTrade({ ...caseJim, probability: 0.8 });
    expect(r.netProfitPct).toBeCloseTo(1.4, 6);
    expect(r.verdict).toBe("reject");
    expect(r.reasons.join(" ")).toContain("سود خالص");
  });

  it("مرز RR دقیقاً ۲ و سود خالص دقیقاً ۲٪ قبول می‌شود", () => {
    // W=2.4 (هدف 3٪ منهای 0.6٪) و L=1.2 ⇒ RR=2 ⇒ دقیقاً روی کف.
    const r = evaluateTrade({ entry: 100, target: 103, stop: 99.4, costPct: 0.6, filter, probability: 0.6 });
    expect(r.netProfitPct).toBeCloseTo(2.4, 6);
    expect(r.riskReward).toBeCloseTo(2, 6);
    expect(r.verdict).toBe("opportunity");
  });

  it("خطای ورودی غیرعددی رد می‌شود (بدون تقسیم بر صفر)", () => {
    const r = evaluateTrade({ entry: 0, target: 10, stop: 1, costPct: 0.6, filter });
    expect(r.verdict).toBe("reject");
    expect(r.riskReward).toBeNull();

    const nan = evaluateTrade({ entry: 100, target: 104, stop: 99, costPct: Number.NaN, filter });
    expect(nan.verdict).toBe("reject");
  });

  it("اگر EV با p معتبر منفی شود، سیگنال صادر نمی‌شود", () => {
    const r = evaluateTrade({ ...caseAlef, probability: 0.1 });
    expect(r.expectedValuePct).toBeLessThan(0);
    expect(r.verdict).toBe("reject");
    expect(r.reasons.join(" ")).toContain("ارزش مورد انتظار");
  });
});

/* ─────────────── §۲۶ هم‌ترازی با گیت سرور ─────────────── */

describe("minimumTargetForFilter (§۲۶ — همان کف گیت signal_decision_engine)", () => {
  const costs = roundTripFeePct(rules, "commodity_fund") as number; // ۰٫۲۴٪

  it("وقتی کف سود خالص تعیین‌کننده است، هدف را از آن می‌سازد", () => {
    const req = minimumTargetForFilter({ entry: 100, riskPct: 0.5, costPct: costs, filter });
    // g* = max(2 + 0.24, 2×(0.5 + 0.24) + 0.24) = 2.24
    expect(req?.binding).toBe("net_profit");
    expect(req?.grossPct).toBeCloseTo(2.24, 6);
    expect(req?.target).toBeCloseTo(102.24, 6);
  });

  it("وقتی نسبت ریسک/ریوارد تعیین‌کننده است، هدف را از آن می‌سازد", () => {
    const req = minimumTargetForFilter({ entry: 100, riskPct: 5, costPct: costs, filter });
    // g* = 2×(5 + 0.24) + 0.24 = 10.72
    expect(req?.binding).toBe("risk_reward");
    expect(req?.grossPct).toBeCloseTo(10.72, 6);
    expect(req?.target).toBeCloseTo(110.72, 6);
  });

  it("هدف ساخته‌شده دقیقاً روی هر دو کف می‌نشیند، نه یک مو پایین‌تر", () => {
    const req = minimumTargetForFilter({ entry: 100, riskPct: 5, costPct: costs, filter });
    const atFloor = evaluateTrade({
      entry: 100,
      target: req!.target,
      stop: 95,
      costPct: costs,
      filter,
      probability: 0.6,
    });
    expect(atFloor.netProfitPct).toBeGreaterThanOrEqual(filter.min_net_profit_pct - 1e-9);
    expect(atFloor.riskReward).toBeGreaterThanOrEqual(filter.min_risk_reward - 1e-9);
    expect(atFloor.verdict).toBe("opportunity");

    const aBitLower = evaluateTrade({
      entry: 100,
      target: req!.target - 0.01,
      stop: 95,
      costPct: costs,
      filter,
      probability: 0.6,
    });
    expect(aBitLower.verdict).toBe("reject");
  });

  it("آستانه‌های سروشده تعیین‌کننده‌اند، نه ثابت ماژول", () => {
    const strict = { ...filter, min_net_profit_pct: 6, min_risk_reward: 4 };
    const profitBound = minimumTargetForFilter({ entry: 100, riskPct: 0.5, costPct: costs, filter: strict });
    expect(profitBound?.binding).toBe("net_profit");
    expect(profitBound?.grossPct).toBeCloseTo(6.24, 6);

    const rrBound = minimumTargetForFilter({ entry: 100, riskPct: 3, costPct: costs, filter: strict });
    expect(rrBound?.binding).toBe("risk_reward");
    expect(rrBound?.grossPct).toBeCloseTo(4 * (3 + costs) + costs, 6);
  });

  it("برای پوزیشن فروش هدف زیر ورود ساخته می‌شود و فیلتر همان معنا را می‌دهد", () => {
    const req = minimumTargetForFilter({
      entry: 100,
      riskPct: 5,
      costPct: costs,
      filter,
      direction: "short",
    });
    expect(req?.target).toBeCloseTo(89.28, 6);

    const r = evaluateTrade({
      entry: 100,
      target: req!.target,
      stop: 105,
      costPct: costs,
      direction: "short",
      filter,
      probability: 0.6,
    });
    expect(r.netProfitPct).toBeCloseTo(10.48, 6);
    expect(r.netRiskPct).toBeCloseTo(5.24, 6);
    expect(r.riskReward).toBeCloseTo(2, 6);
    expect(r.verdict).toBe("opportunity");
  });

  it("ورودی نامعتبر ⇒ null؛ هیچ آستانه‌ای جایگزین نمی‌شود (§۱۳)", () => {
    expect(minimumTargetForFilter({ entry: 0, riskPct: 1, costPct: costs, filter })).toBeNull();
    expect(minimumTargetForFilter({ entry: 100, riskPct: -1, costPct: costs, filter })).toBeNull();
    expect(
      minimumTargetForFilter({ entry: 100, riskPct: 1, costPct: Number.NaN, filter }),
    ).toBeNull();
    // ریسک خالص صفر ⇒ RR تعریف‌نشده
    expect(minimumTargetForFilter({ entry: 100, riskPct: 0, costPct: 0, filter })).toBeNull();
  });
});

describe("evaluateTrade با جهت فروش", () => {
  it("هدف زیر ورود و حد ضرر بالای ورود ⇒ سود و ریسک هر دو مثبت", () => {
    const r = evaluateTrade({
      entry: 100,
      target: 97,
      stop: 101,
      costPct: 0.6,
      direction: "short",
      filter,
      probability: 0.6,
    });
    expect(r.netProfitPct).toBeCloseTo(2.4, 6);
    expect(r.netRiskPct).toBeCloseTo(1.6, 6);
    expect(r.riskReward).toBeCloseTo(1.5, 6);
    expect(r.verdict).toBe("reject"); // RR = 1.5 < 2
  });

  it("پوزیشن فروشی که حد ضررش زیر ورود است، ریسک نامعتبر دارد و رد می‌شود", () => {
    const r = evaluateTrade({
      entry: 100,
      target: 97,
      stop: 99,
      costPct: 0.6,
      direction: "short",
      filter,
    });
    expect(r.netRiskPct).toBeLessThan(0);
    expect(r.riskReward).toBeNull();
    expect(r.verdict).toBe("reject");
  });
});

/* ─────────────── §۲۷.۳ ساعت بازار ─────────────── */

describe("ساعت بازار (§۲۷.۳)", () => {
  const hours = rules.market_hours;

  it("شنبه تا چهارشنبه ۱۲:۰۰ تا ۱۸:۰۰ با پیش‌گشایش ۱۱:۴۵ است", () => {
    expect(hours.sat_to_wed).toEqual({ pre_open: "11:45", open: "12:00", close: "18:00" });
    expect(sessionForWeekday(hours, 0)).toEqual(hours.sat_to_wed);
    expect(sessionForWeekday(hours, 4)).toEqual(hours.sat_to_wed);
  });

  it("پنجشنبه جلسهٔ کوتاه ۱۲:۰۰ تا ۱۵:۰۰ دارد", () => {
    expect(sessionForWeekday(hours, 5)).toEqual({
      pre_open: "11:45",
      open: "12:00",
      close: "15:00",
    });
  });

  it("جمعه تعطیل است", () => {
    expect(sessionForWeekday(hours, 6)).toBeNull();
    expect(sessionState(hours, 6, "13:00")).toBeNull();
  });

  it("دامنهٔ نوسان ۱۰٪، دامنه‌های اضطراری و تسویه T+1 است", () => {
    expect(hours.price_band_pct).toBe(10);
    expect(hours.emergency_band_pcts).toEqual([1, 2, 5]);
    expect(settlementLabel(hours.settlement_days)).toBe("T+1");
  });

  it("وضعیت جلسه در مرزها درست است", () => {
    expect(sessionState(hours, 0, "11:44")).toBe("closed");
    expect(sessionState(hours, 0, "11:45")).toBe("pre_open");
    expect(sessionState(hours, 0, "11:59")).toBe("pre_open");
    expect(sessionState(hours, 0, "12:00")).toBe("open");
    expect(sessionState(hours, 0, "18:00")).toBe("open");
    expect(sessionState(hours, 0, "18:01")).toBe("after_close");
    // پنجشنبه همان ۱۵:۰۰ می‌بندد، نه ۱۸:۰۰
    expect(sessionState(hours, 5, "15:01")).toBe("after_close");
    expect(sessionState(hours, 5, "14:59")).toBe("open");
  });

  it("minutesOfDay «HH:MM» را به دقیقه تبدیل می‌کند", () => {
    expect(minutesOfDay("00:00")).toBe(0);
    expect(minutesOfDay("11:45")).toBe(705);
    expect(minutesOfDay("18:00")).toBe(1080);
  });
});

describe("tehranClock", () => {
  it("ساعت دیوارساعت تهران را می‌دهد (UTC+۳:۳۰، بدون تغییر ساعت)", () => {
    // ۲۰۲۶-۱۰-۱۴ ساعت ۰۸:۰۰ UTC = چهارشنبه ۱۱:۳۰ تهران
    expect(tehranClock(new Date("2026-10-14T08:00:00Z"))).toEqual({ day: 4, hhmm: "11:30" });
    // همان روز، ۱۴:۳۰ UTC = ساعت ۱۸:۰۰ تهران (دقیقاً بستن)
    expect(tehranClock(new Date("2026-10-14T14:30:00Z")).hhmm).toBe("18:00");
  });

  it("پنجشنبه را روز ۵ و جمعه را روز ۶ می‌شناسد", () => {
    expect(tehranClock(new Date("2026-10-15T08:00:00Z")).day).toBe(5); // Thu
    expect(tehranClock(new Date("2026-10-16T08:00:00Z")).day).toBe(6); // Fri
  });

  it("ساعت تهران با وضعیت جلسه سازگار است", () => {
    const { day, hhmm } = tehranClock(new Date("2026-10-14T14:30:00Z")); // Wed 18:00
    expect(sessionState(rules.market_hours, day, hhmm)).toBe("open");
  });
});
