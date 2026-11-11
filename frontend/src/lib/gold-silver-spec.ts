/**
 * قواعد مشترک صفحه‌های طلا و نقره: توابع خالص + تحلیل‌گر پاسخ API.
 *
 * ⚠️ این فایل **هیچ عددی** ندارد. تعرفهٔ §۲۷.۱، آستانه‌های فیلتر §۲۶ و ساعت بازار
 * §۲۷.۳ از ``GET /gold/assistant-rules`` خوانده می‌شوند که خودش تنها منبعشان
 * ``acceptance.yaml`` است؛ پس موتور سیگنال سمت سرور (`signal_decision_engine`) و
 * این صفحه‌ها یک عدد را نشان می‌دهند و درِ دومِ حقیقت ساخته نمی‌شود.
 *
 * اگر پیکربندی ناقص برگردد، ``parseAssistantRules`` **خطای صریح** می‌دهد و هیچ
 * عدد پیش‌فرضی جایگزین نمی‌شود؛ چون «صفر» یک هزینهٔ جعلی و «۲» یک آستانهٔ جعلی
 * می‌سازد (§۲۷.۱ و §۲۸.۲ — هم‌راستا با بند §۱۳ سند).
 *
 * ⚠️ مقادیری که ``provenance`` آن‌ها ``assumption`` است پیشنهاد نویسندهٔ سند و
 * منتظر تأیید مالک‌اند (§۲۸.۲) و باید با همان برچسب نمایش داده شوند، نه قطعی.
 */

export type Provenance = "spec" | "assumption" | "unavailable";

/* ─────────────── §۲۷.۱ تعرفه ─────────────── */

export type InstrumentKind =
  | "commodity_fund"
  | "coin_certificate"
  | "bullion_certificate"
  | "futures"
  | "option";

/** تعرفهٔ یک ابزار — شکل دقیق پاسخ API. */
export interface FeeTerms {
  label_fa: string;
  /** کارمزد هر سمت به‌صورت کسر (۰٫۱۲٪ → 0.0012). `null` یعنی عدد قابل‌اتکا نبود. */
  fee_per_side: number | null;
  /** سقف کارمزد هر سمت به ریال. `null` یعنی سقف ندارد. */
  fee_cap_irr: number | null;
  tax_exempt: boolean;
  provenance: Provenance;
  /** کارمزد رفت‌وبرگشت به کسر؛ فقط وقتی هر دو سمت نرخ دارند عدد می‌شود. */
  round_trip_fee_per_side: number | null;
  note?: string;
}

export interface FeeSchedule {
  version: string;
  last_updated: string;
  instruments: Record<string, FeeTerms>;
}

/* ─────────────── §۲۶ فیلتر ارزش معامله ─────────────── */

export interface SignalFilter {
  /** سود خالص هدف — خواستهٔ مالک، در همهٔ بازارها (§۲۶). */
  min_net_profit_pct: number;
  /** نسبت ریسک به ریوارد (§۲۶) — گیت سرور هم همین کف را اعمال می‌کند. */
  min_risk_reward: number;
  /** `EV` باید مثبت باشد؛ فقط با `p` معتبر از بک‌تست قابل محاسبه است (§۲۶). */
  require_positive_ev: boolean;
  provenance: Record<string, Provenance>;
}

/* ─────────────── §۲۷.۳ ساعت، دامنه و تسویه ─────────────── */

export interface SessionHours {
  /** «HH:MM» به وقت تهران. */
  pre_open: string;
  open: string;
  close: string;
}

export interface MarketHours {
  /** شنبه تا چهارشنبه — پایان معاملات صندوق‌ها/گواهی‌ها/مشتقه (§۲۷.۳). */
  sat_to_wed: SessionHours;
  /** پنجشنبه — جلسهٔ کوتاه (§۲۷.۳). */
  thursday: SessionHours;
  friday_closed: boolean;
  /** دامنهٔ نوسان روزانه بر پایهٔ قیمت پایانی روز قبل (§۲۷.۳). */
  price_band_pct: number;
  /** دامنه‌های اضطراری — سامانه باید `tmin`/`tmax` روز را بخواند. */
  emergency_band_pcts: number[];
  /** تسویهٔ صندوق و گواهی: `T+1` (§۲۷.۳). */
  settlement_days: number;
  provenance: Provenance;
}

/** بستهٔ کامل قواعد دستیار — همان چیزی که API سرو می‌کند. */
export interface AssistantRules {
  version: string;
  fee_schedule: FeeSchedule;
  signal_filter: SignalFilter;
  market_hours: MarketHours;
}

/* ─────────────── تحلیل و اعتبارسنجی پاسخ API ─────────────── */

/** پیکربندی معیوب باید بی‌صدا عبور نکند (§۱۳). */
export class AssistantRulesError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AssistantRulesError";
  }
}

const fail = (path: string, expected: string): never => {
  throw new AssistantRulesError(`${path} نامعتبر است: ${expected}`);
};

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

function readRecord(value: unknown, path: string): Record<string, unknown> {
  return isRecord(value) ? value : fail(path, "شیء مورد انتظار بود");
}

function readNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fail(path, "عدد متناهی");
  return value;
}

function readNumberOrNull(value: unknown, path: string): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isFinite(value)) return fail(path, "عدد یا null");
  return value;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim() === "") return fail(path, "رشتهٔ غیرخالی");
  return value;
}

function readBool(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") return fail(path, "true یا false");
  return value;
}

function readProvenance(value: unknown, path: string): Provenance {
  if (value === "spec" || value === "assumption" || value === "unavailable") return value;
  return fail(path, "یکی از spec | assumption | unavailable");
}

function parseSessionHours(value: unknown, path: string): SessionHours {
  const raw = readRecord(value, path);
  return {
    pre_open: readString(raw.pre_open, `${path}.pre_open`),
    open: readString(raw.open, `${path}.open`),
    close: readString(raw.close, `${path}.close`),
  };
}

/**
 * پاسخ ``GET /gold/assistant-rules`` را به مدل تایپ‌شده تبدیل می‌کند.
 *
 * هر مقدار مفقود یا نامعتبر خطای ``AssistantRulesError`` می‌دهد تا صفحه به‌جای
 * نشان‌دادن یک عدد ساختگی، صریحاً بگوید «قواعد در دسترس نیست».
 */
export function parseAssistantRules(raw: unknown): AssistantRules {
  const root = readRecord(raw, "assistant_rules");

  const scheduleRaw = readRecord(root.fee_schedule, "fee_schedule");
  const instrumentsRaw = readRecord(scheduleRaw.instruments, "fee_schedule.instruments");
  const instruments: Record<string, FeeTerms> = {};
  for (const [kind, termsRaw] of Object.entries(instrumentsRaw)) {
    const terms = readRecord(termsRaw, `fee_schedule.instruments.${kind}`);
    instruments[kind] = {
      label_fa: readString(terms.label_fa, `fee_schedule.instruments.${kind}.label_fa`),
      fee_per_side: readNumberOrNull(
        terms.fee_per_side,
        `fee_schedule.instruments.${kind}.fee_per_side`,
      ),
      fee_cap_irr: readNumberOrNull(
        terms.fee_cap_irr,
        `fee_schedule.instruments.${kind}.fee_cap_irr`,
      ),
      tax_exempt: readBool(terms.tax_exempt, `fee_schedule.instruments.${kind}.tax_exempt`),
      provenance: readProvenance(
        terms.provenance,
        `fee_schedule.instruments.${kind}.provenance`,
      ),
      round_trip_fee_per_side: readNumberOrNull(
        terms.round_trip_fee_per_side,
        `fee_schedule.instruments.${kind}.round_trip_fee_per_side`,
      ),
      ...(typeof terms.note === "string" ? { note: terms.note } : {}),
    };
  }
  if (Object.keys(instruments).length === 0) {
    fail("fee_schedule.instruments", "دست‌کم یک ابزار");
  }

  const filterRaw = readRecord(root.signal_filter, "signal_filter");
  const minNetProfitPct = readNumber(
    filterRaw.min_net_profit_pct,
    "signal_filter.min_net_profit_pct",
  );
  const minRiskReward = readNumber(filterRaw.min_risk_reward, "signal_filter.min_risk_reward");
  if (minNetProfitPct <= 0) {
    fail("signal_filter.min_net_profit_pct", "عدد مثبت (§۲۶)");
  }
  if (minRiskReward <= 0) {
    fail("signal_filter.min_risk_reward", "عدد مثبت (§۲۶ «حداقل ۲ به ۱»)");
  }

  const provenanceRaw = readRecord(filterRaw.provenance, "signal_filter.provenance");
  const provenance: Record<string, Provenance> = {};
  for (const [key, value] of Object.entries(provenanceRaw)) {
    provenance[key] = readProvenance(value, `signal_filter.provenance.${key}`);
  }

  const hoursRaw = readRecord(root.market_hours, "market_hours");
  const emergencyRaw = hoursRaw.emergency_band_pcts;
  if (!Array.isArray(emergencyRaw) || emergencyRaw.some((v) => typeof v !== "number")) {
    fail("market_hours.emergency_band_pcts", "آرایهٔ عددی");
  }

  return {
    version: readString(root.version, "version"),
    fee_schedule: {
      version: readString(scheduleRaw.version, "fee_schedule.version"),
      last_updated: readString(scheduleRaw.last_updated, "fee_schedule.last_updated"),
      instruments,
    },
    signal_filter: {
      min_net_profit_pct: minNetProfitPct,
      min_risk_reward: minRiskReward,
      require_positive_ev: readBool(
        filterRaw.require_positive_ev,
        "signal_filter.require_positive_ev",
      ),
      provenance,
    },
    market_hours: {
      sat_to_wed: parseSessionHours(hoursRaw.sat_to_wed, "market_hours.sat_to_wed"),
      thursday: parseSessionHours(hoursRaw.thursday, "market_hours.thursday"),
      friday_closed: readBool(hoursRaw.friday_closed, "market_hours.friday_closed"),
      price_band_pct: readNumber(hoursRaw.price_band_pct, "market_hours.price_band_pct"),
      emergency_band_pcts: emergencyRaw as number[],
      settlement_days: readNumber(hoursRaw.settlement_days, "market_hours.settlement_days"),
      provenance: readProvenance(hoursRaw.provenance, "market_hours.provenance"),
    },
  };
}

/* ─────────────── تعرفه: مشتق‌های خالص ─────────────── */

/** کارمزد رفت‌وبرگشت به **درصد**؛ `null` اگر ابزار نرخ قابل‌اتکا نداشته باشد. */
export function roundTripFeePct(
  rules: AssistantRules,
  kind: InstrumentKind,
): number | null {
  const trip = rules.fee_schedule.instruments[kind]?.round_trip_fee_per_side;
  return trip == null ? null : trip * 100;
}

/** تعرفهٔ یک ابزار؛ `null` اگر آن ابزار در پاسخ API نباشد. */
export function feeTerms(
  rules: AssistantRules,
  kind: InstrumentKind,
): FeeTerms | null {
  return rules.fee_schedule.instruments[kind] ?? null;
}

/* ─────────────── §۲۰ حرکت ناخالص لازم ─────────────── */

/**
 * کمترین حرکت ناخالص لازم برای رسیدن به هدف خالص (§۲۰):
 *   `g* = target + c_buy + c_sell + s + ℓ`
 * همهٔ ورودی‌ها به درصد.
 */
export function requiredGrossMovePct(input: {
  targetNetPct: number;
  buyFeePct: number;
  sellFeePct: number;
  spreadPct?: number;
  slippagePct?: number;
  otherPct?: number;
}): number {
  const {
    targetNetPct,
    buyFeePct,
    sellFeePct,
    spreadPct = 0,
    slippagePct = 0,
    otherPct = 0,
  } = input;
  return targetNetPct + buyFeePct + sellFeePct + spreadPct + slippagePct + otherPct;
}

/**
 * حداقل حرکت ناخالص لازم برای ابزارهای فیزیکی‌محور با آستانه و تعرفهٔ سروشده.
 * `null` وقتی تعرفهٔ آن ابزار «ناموجود» است — عدد ساختگی جایگزین نمی‌شود (§۲۷.۱).
 */
export function requiredGrossMovePctFor(
  rules: AssistantRules,
  kind: InstrumentKind = "commodity_fund",
): number | null {
  const trip = roundTripFeePct(rules, kind);
  if (trip === null) return null;
  return requiredGrossMovePct({
    targetNetPct: rules.signal_filter.min_net_profit_pct,
    buyFeePct: trip / 2,
    sellFeePct: trip / 2,
  });
}

/* ─────────────── §۲۰/§۲۶ سود، ریسک، RR و EV ─────────────── */

export type SignalVerdict = "opportunity" | "watch" | "reject";

/**
 * برچسب نمایشی هر حکم — یک متن برای همهٔ صفحه‌ها، تا «سیگنال صادر نشد» در یک
 * صفحه «رد» و در صفحهٔ دیگر «فرصت» ترجمه نشود.
 */
export const SIGNAL_VERDICT_LABEL: Record<SignalVerdict, string> = {
  opportunity: "بررسی فرصت — سیگنال صادر می‌شود",
  watch: "فقط پایش — EV نامشخص",
  reject: "سیگنال صادر نشد",
};

/** جهت پوزیشن؛ سطوح هدف و حد ضرر نسبت به ورود آینه می‌شوند. */
export type TradeDirection = "long" | "short";

export interface TradeEvaluation {
  /** کسر هزینهٔ رفت‌وبرگشت که در فرمول‌ها استفاده شد. */
  costPct: number;
  /** `W = (T − E)/E − C` به درصد. */
  netProfitPct: number | null;
  /** `L = (E − S)/E + C` به درصد. */
  netRiskPct: number | null;
  /** `RR = W / L`؛ `null` وقتی `L` صفر یا نامعتبر است. */
  riskReward: number | null;
  /** `EV = p·W − (1 − p)·L` به درصد؛ `null` یعنی `p` معتبر نیست. */
  expectedValuePct: number | null;
  verdict: SignalVerdict;
  /** دلیل‌های عددی رد یا «پایش» — هرگز خالی برای verdict≠opportunity. */
  reasons: string[];
}

/**
 * فیلتر §۲۶ روی یک معاملهٔ نامزد. ورودی‌ها به درصد (نه کسر) گرفته می‌شوند تا با
 * نمایش صفحه یکی باشند.
 *
 * `filter` **الزامی** است و از پاسخ API می‌آید تا آستانه‌ای در این فایل هاردکد
 * نشود و با گیت سمت سرور یکی بماند.
 *
 * `probability` اگر معتبر (۰ تا ۱) داده نشود، `EV` «نامشخص» می‌ماند و نتیجه
 * حداکثر «پایش» است، نه «بررسی فرصت» (§۲۶).
 *
 * `direction` فقط علامت فاصله‌ها را برمی‌گرداند؛ سود و ریسک **همیشه به درصد
 * اندازه** سنجیده می‌شوند تا فیلتر §۲۶ روی پوزیشن فروش هم همان معنا را بدهد.
 */
export function evaluateTrade(input: {
  entry: number;
  target: number;
  stop: number;
  costPct: number;
  probability?: number | null;
  filter: SignalFilter;
  direction?: TradeDirection;
}): TradeEvaluation {
  const { filter, entry, target, stop } = input;
  const costPct = input.costPct;
  const direction: TradeDirection = input.direction === "short" ? "short" : "long";
  const sign = direction === "short" ? -1 : 1;

  if (!(entry > 0) || !(target > 0) || !(stop > 0)) {
    return {
      costPct,
      netProfitPct: null,
      netRiskPct: null,
      riskReward: null,
      expectedValuePct: null,
      verdict: "reject",
      reasons: ["ورود، هدف و حد ضرر باید عددی مثبت باشند"],
    };
  }

  const netProfitPct = ((sign * (target - entry)) / entry) * 100 - costPct;
  const netRiskPct = ((sign * (entry - stop)) / entry) * 100 + costPct;
  const riskReward = netRiskPct > 0 ? netProfitPct / netRiskPct : null;

  const reasons: string[] = [];
  if (netProfitPct < filter.min_net_profit_pct) {
    reasons.push(
      `سود خالص ${netProfitPct.toFixed(2)}٪ کمتر از حداقل ${filter.min_net_profit_pct}٪ است (§۲۶)`,
    );
  }
  if (riskReward === null) {
    reasons.push("ریسک خالص صفر یا نامعتبر است، پس نسبت ریسک/ریوارد محاسبه‌شدنی نیست");
  } else if (riskReward < filter.min_risk_reward) {
    reasons.push(
      `نسبت ریسک/ریوارد ${riskReward.toFixed(2)} کمتر از ${filter.min_risk_reward} است (§۲۶)`,
    );
  }

  // شکست شرط سود خالص یا RR یعنی «سیگنال صادر نشد» — نه «پایش» (§۲۶).
  if (reasons.length > 0) {
    return {
      costPct,
      netProfitPct,
      netRiskPct,
      riskReward,
      expectedValuePct: null,
      verdict: "reject",
      reasons,
    };
  }

  const probability = input.probability;
  const hasProbability = typeof probability === "number" && probability > 0 && probability < 1;

  if (!hasProbability) {
    // `p` معتبر نیست ⇒ `EV` نامشخص ⇒ سقف خروجی «پایش»، نه «بررسی فرصت» (§۲۶).
    return {
      costPct,
      netProfitPct,
      netRiskPct,
      riskReward,
      expectedValuePct: null,
      verdict: "watch",
      reasons: [
        "احتمال موفقیت (p) معتبر از بک‌تست نیست؛ EV نامشخص و سقف نتیجه «پایش» است (§۲۶)",
      ],
    };
  }

  const p: number = probability;
  const expectedValuePct = p * netProfitPct - (1 - p) * netRiskPct;

  if (filter.require_positive_ev && expectedValuePct <= 0) {
    return {
      costPct,
      netProfitPct,
      netRiskPct,
      riskReward,
      expectedValuePct,
      verdict: "reject",
      reasons: [`ارزش مورد انتظار ${expectedValuePct.toFixed(2)}٪ مثبت نیست (§۲۶)`],
    };
  }

  return {
    costPct,
    netProfitPct,
    netRiskPct,
    riskReward,
    expectedValuePct,
    verdict: "opportunity",
    reasons: [],
  };
}

/* ─────────────── §۲۶ حداقل هدف برای عبور از فیلتر ─────────────── */

/** کدام کف §۲۶ هدف را تعیین کرد. */
export type FilterBinding = "net_profit" | "risk_reward";

export interface FilterTargetRequirement {
  /** حرکت ناخالص لازم از ورود تا هدف (٪) — `g*` سند §۲۰/§۲۶. */
  grossPct: number;
  /** قیمت هدف لازم؛ زیر ورود برای پوزیشن فروش. */
  target: number;
  /** کفِ تعیین‌کننده: سود خالص یا نسبت ریسک/ریوارد. */
  binding: FilterBinding;
}

/**
 * کمترین هدفی که **هر دو** کف §۲۶ را رد می‌کند — دقیقاً همان دو شرطی که گیت
 * `signal_decision_engine` روی `target_pct` و `risk_reward` می‌سنجد:
 *
 *   `W = g − c ≥ min_net_profit_pct  ⇒  g ≥ min_net_profit_pct + c`
 *   `RR = (g − c) / (r + c) ≥ min_risk_reward  ⇒  g ≥ min_risk_reward·(r + c) + c`
 *
 * که `r` ریسک ناخالص تا حد ضرر (٪) و `c` هزینهٔ رفت‌وبرگشت (٪) است. خروجی `null`
 * یعنی ورودی نامعتبر است و آستانه‌ای جایگزین نمی‌شود (§۱۳).
 */
export function minimumTargetForFilter(input: {
  entry: number;
  riskPct: number;
  costPct: number;
  filter: SignalFilter;
  direction?: TradeDirection;
}): FilterTargetRequirement | null {
  const { entry, riskPct, costPct, filter } = input;
  if (!Number.isFinite(entry) || entry <= 0) return null;
  if (!Number.isFinite(riskPct) || riskPct < 0) return null;
  if (!Number.isFinite(costPct) || costPct < 0) return null;

  // ریسک خالص صفر ⇒ `RR` تعریف‌نشده؛ عدد جعلی ساخته نمی‌شود (§۲۶).
  const netRiskPct = riskPct + costPct;
  if (netRiskPct <= 0) return null;

  const grossFromNetProfit = filter.min_net_profit_pct + costPct;
  const grossFromRiskReward = filter.min_risk_reward * netRiskPct + costPct;
  const exactGrossPct = Math.max(grossFromNetProfit, grossFromRiskReward);
  // هدف دقیقاً روی کف می‌نشیند و گیت سرور با `<` مقایسه می‌کند؛ پس یک حاشیهٔ ناچیز
  // نسبی می‌گذاریم تا خطای ممیز شناور، RR را ۱٫۹۹۹۹۹۹۹ نکند و همان عددی که صفحه
  // نشان می‌دهد، دروازه را رد کند.
  const grossPct = exactGrossPct * (1 + 1e-9) + 1e-9;
  const direction: TradeDirection = input.direction === "short" ? "short" : "long";

  return {
    grossPct,
    target: direction === "short" ? entry * (1 - grossPct / 100) : entry * (1 + grossPct / 100),
    binding: grossFromNetProfit >= grossFromRiskReward ? "net_profit" : "risk_reward",
  };
}

/* ─────────────── §۲۷.۳ ساعت جلسه ─────────────── */

/** روز هفتهٔ ایرانی: ۰=شنبه … ۶=جمعه. */
export type IranWeekday = 0 | 1 | 2 | 3 | 4 | 5 | 6;

/** شنبه(۰) تا چهارشنبه(۴) معامله می‌شود، پنجشنبه(۵) جلسهٔ کوتاه، جمعه(۶) تعطیل. */
export function sessionForWeekday(hours: MarketHours, day: IranWeekday): SessionHours | null {
  if (day >= 0 && day <= 4) return hours.sat_to_wed;
  if (day === 5) return hours.thursday;
  return null;
}

/** «HH:MM» → دقیقه از نیمه‌شب؛ برای مقایسهٔ بازه‌ای. */
export function minutesOfDay(hhmm: string): number {
  const [h, m] = hhmm.split(":").map((x) => Number.parseInt(x, 10));
  return h * 60 + m;
}

export type SessionState = "closed" | "pre_open" | "open" | "after_close";

/**
 * وضعیت جلسه از ساعت دیوارساعت تهران. خروجی `null` یعنی جمعه (بازار غیرفعال).
 * تابع خالص است تا در تست بدون وابستگی به ساعت سیستم قابل بررسی باشد.
 */
export function sessionState(
  hours: MarketHours,
  day: IranWeekday,
  hhmm: string,
): SessionState | null {
  const session = sessionForWeekday(hours, day);
  if (!session) return null;
  const now = minutesOfDay(hhmm);
  if (now < minutesOfDay(session.pre_open)) return "closed";
  if (now < minutesOfDay(session.open)) return "pre_open";
  if (now <= minutesOfDay(session.close)) return "open";
  return "after_close";
}

/** ساعت دیوارساعت تهران به‌صورت «HH:MM» (برای نمایش وضعیت جلسه). */
export function tehranClock(now: Date = new Date()): { day: IranWeekday; hhmm: string } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Tehran",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);

  const raw = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  const hhmm = `${raw.hour === "24" ? "00" : raw.hour}:${raw.minute}`;

  // Intl روز را به انگلیسی می‌دهد؛ نگاشت به روز هفتهٔ ایرانی.
  const map: Record<string, IranWeekday> = {
    Sat: 0,
    Sun: 1,
    Mon: 2,
    Tue: 3,
    Wed: 4,
    Thu: 5,
    Fri: 6,
  };
  const day = map[raw.weekday ?? ""] ?? 0;
  return { day, hhmm };
}

/** برچسب تسویه از تعداد روز سروشده — بدون عدد هاردکد. */
export function settlementLabel(days: number): string {
  return days === 0 ? "T+0 (نقدی)" : `T+${days}`;
}

/* ─────────────── برچسب‌های ثابت (متن سند، نه عدد) ─────────────── */

export const SESSION_STATE_LABEL: Record<SessionState | "holiday", string> = {
  closed: "پیش از گشایش",
  pre_open: "پیش‌گشایش",
  open: "باز",
  after_close: "پس از بستن",
  holiday: "تعطیل (جمعه)",
};

/** معنای `provenance` برای نمایش کنار هر عدد (§۲۸.۲). */
export const PROVENANCE_LABEL: Record<Provenance, string> = {
  spec: "سند",
  assumption: "فرض — منتظر تأیید مالک (§۲۸.۲)",
  unavailable: "ناموجود — عدد قابل‌اتکا پیدا نشد (§۲۷.۱)",
};

/**
 * §۲۴: تحویل فیزیکی خارج از دامنه است. قیمت فیزیکی فقط ورودی تحلیل است.
 * صفحه باید این جمله را نشان دهد تا بین «نمایش قیمت» و «سیگنال» اشتباه نشود.
 */
export const PHYSICAL_DELIVERY_NOTE =
  "طلا و نقرهٔ فیزیکی (تحویل، انبارداری، ضرب) در دامنه نیست؛ قیمت فیزیکی فقط ورودی تحلیل ابزارهای غیرفیزیکی است (§۲۴).";

/** هر عدد سند باید با منبع و زمانش نمایش داده شود (§۵). */
export const DISCLAIMER =
  "تحلیل، مشاورهٔ قطعی مالی نیست و تصمیم نهایی با شماست. این صفحه فقط سیگنال/تحلیل ارائه می‌دهد و هیچ سفارشی ثبت نمی‌کند (§۱ و §۵).";
