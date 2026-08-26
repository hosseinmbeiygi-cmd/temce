import {
  FUND_CHECKLIST_ITEMS,
  FUND_CHECKLIST_AREA_ORDER,
  normalizeChecklistImportance,
  normalizeChecklistStatus,
  scoreChecklistItem,
  type FundChecklistItem,
} from "@/lib/fund-checklist";

export interface FundChecklistFundLike {
  symbol: string;
  name: string;
  isin?: string;
  fund_type?: string;
  market?: string;
  nav: number;
  nav_change: number;
  nav_change_pct: number;
  price_last: number;
  price_close: number;
  price_yesterday: number;
  price_max: number;
  price_min: number;
  trade_volume: number;
  trade_value: number;
  trade_count: number;
  shares_count: number;
  base_volume: number;
  market_value: number;
  buy_real_volume: number;
  buy_legal_volume: number;
  sell_real_volume: number;
  sell_legal_volume: number;
  snapshot_date?: string;
  nav_source?: string;
  nav_date?: string;
  time?: string;
  updated_at?: string;
  nav_history?: Array<{ date: string; nav: number; source?: string }>;
  nav_history_points?: number;
  analysis?: {
    scores: {
      financial: number;
      liquidity: number;
      management: number;
      risk: number;
      cost: number;
      transparency: number;
      total: number;
    };
    recommendation: string;
    risk_level: string;
    issues_count: number;
    summary: string;
  };
}

export interface FundChecklistSymbolDetailLike {
  symbol: string;
  name?: string | null;
  isin?: string | null;
  market?: string | null;
  board?: string | null;
  sector?: string | null;
  sub_sector?: string | null;
  state?: string | null;
  shares_count?: number | null;
  shares_issued?: number | null;
  base_volume?: number | null;
  market_value?: number | null;
  free_float_pct?: number | null;
  eps?: number | null;
  pe_ratio?: number | null;
  group_pe_ratio?: number | null;
  ps_ratio?: number | null;
  price_lowest_allowed?: number | null;
  price_highest_allowed?: number | null;
  price_min_week?: number | null;
  price_max_week?: number | null;
  price_min_year?: number | null;
  price_max_year?: number | null;
  price_min?: number | null;
  price_max?: number | null;
  price_yesterday?: number | null;
  price_first?: number | null;
  price_last?: number | null;
  price_last_change?: number | null;
  price_last_change_pct?: number | null;
  price_close?: number | null;
  price_close_change?: number | null;
  price_close_change_pct?: number | null;
  trade_count?: number | null;
  trade_volume?: number | null;
  trade_volume_avg_month?: number | null;
  trade_value?: number | null;
  buy_real_count?: number | null;
  buy_legal_count?: number | null;
  sell_real_count?: number | null;
  sell_legal_count?: number | null;
  buy_real_volume?: number | null;
  buy_legal_volume?: number | null;
  sell_real_volume?: number | null;
  sell_legal_volume?: number | null;
  date?: string | null;
  date_update?: string | null;
  time?: string | null;
  updated_at?: string | null;
}

export interface FundChecklistRowView {
  item: FundChecklistItem;
  score: number;
  importanceLabel: string;
  statusLabel: string;
  realValue: string;
  realSource: string;
  realNote: string;
  availability: "available" | "partial" | "missing";
  confidence: number;
}

export interface FundChecklistSummary {
  totalItems: number;
  availableCount: number;
  partialCount: number;
  missingCount: number;
  averageScore: number;
}

export interface FundChecklistAreaSummary {
  area: string;
  itemCount: number;
  availableCount: number;
  partialCount: number;
  missingCount: number;
  averageScore: number;
}

type FundAnalysisScores = NonNullable<FundChecklistFundLike["analysis"]>["scores"];

function n(v: number | null | undefined): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

function text(v: string | number | null | undefined): string {
  if (v == null || v === "") return "—";
  if (typeof v === "number") return v.toLocaleString("fa-IR", { maximumFractionDigits: 2 });
  return String(v);
}

function pct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toLocaleString("fa-IR", { maximumFractionDigits: 2 })}%`;
}

function money(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${(v / 1e12).toFixed(2)} هزار میلیارد`;
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)} میلیارد`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)} میلیون`;
  return v.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

function combine(...parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join(" / ") || "—";
}

function containsAny(source: string, terms: string[]): boolean {
  return terms.some((term) => source.includes(term));
}

function scoreForAvailability(availability: FundChecklistRowView["availability"], confidence: number): number {
  const base = availability === "available" ? 1 : availability === "partial" ? 0.72 : 0.32;
  return Math.round(Math.min(100, Math.max(0, base * confidence)));
}

function areaDimension(area: string): keyof FundAnalysisScores | null {
  if (area.includes("هویت") || area.includes("شفافیت")) return "transparency";
  if (area.includes("ذخایر")) return "financial";
  if (area.includes("زیرساخت") || area.includes("شبکه") || area.includes("آنچین") || area.includes("بازار تتر")) return "liquidity";
  if (area.includes("اقتصاد توکنی")) return "management";
  if (area.includes("پیگ") || area.includes("ریسک")) return "risk";
  return null;
}

function buildContext(fund: FundChecklistFundLike, symbolDetail?: FundChecklistSymbolDetailLike | null) {
  const navHistory = fund.nav_history ?? [];
  const navHistoryFirst = navHistory[0]?.nav ?? null;
  const navHistoryLast = navHistory.length ? navHistory[navHistory.length - 1].nav : null;
  const navHistoryChangePct = navHistoryFirst && navHistoryLast ? ((navHistoryLast - navHistoryFirst) / navHistoryFirst) * 100 : null;
  const premiumPct = fund.nav > 0 && fund.price_last > 0 ? ((fund.price_last - fund.nav) / fund.nav) * 100 : null;
  const spreadPct = fund.price_max > 0 && fund.price_min > 0 ? ((fund.price_max - fund.price_min) / ((fund.price_max + fund.price_min) / 2)) * 100 : null;
  const rangePct = fund.price_max > 0 && fund.price_min > 0 ? ((fund.price_max - fund.price_min) / ((fund.price_max + fund.price_min) / 2)) * 100 : null;
  return {
    symbol: fund.symbol,
    name: fund.name,
    isin: fund.isin ?? symbolDetail?.isin ?? "",
    market: symbolDetail?.market ?? fund.market ?? "",
    board: symbolDetail?.board ?? "",
    sector: symbolDetail?.sector ?? "",
    subSector: symbolDetail?.sub_sector ?? "",
    state: symbolDetail?.state ?? "",
    nav: fund.nav,
    navChange: fund.nav_change,
    navChangePct: fund.nav_change_pct,
    priceLast: fund.price_last,
    priceClose: fund.price_close,
    priceYesterday: fund.price_yesterday,
    priceMin: fund.price_min,
    priceMax: fund.price_max,
    tradeVolume: fund.trade_volume,
    tradeValue: fund.trade_value,
    tradeCount: fund.trade_count,
    sharesCount: fund.shares_count,
    baseVolume: fund.base_volume,
    marketValue: fund.market_value,
    buyRealVolume: fund.buy_real_volume,
    buyLegalVolume: fund.buy_legal_volume,
    sellRealVolume: fund.sell_real_volume,
    sellLegalVolume: fund.sell_legal_volume,
    buyRealCount: n(symbolDetail?.buy_real_count),
    buyLegalCount: n(symbolDetail?.buy_legal_count),
    sellRealCount: n(symbolDetail?.sell_real_count),
    sellLegalCount: n(symbolDetail?.sell_legal_count),
    sharesIssued: n(symbolDetail?.shares_issued),
    freeFloatPct: symbolDetail?.free_float_pct ?? null,
    eps: symbolDetail?.eps ?? null,
    peRatio: symbolDetail?.pe_ratio ?? null,
    groupPeRatio: symbolDetail?.group_pe_ratio ?? null,
    psRatio: symbolDetail?.ps_ratio ?? null,
    priceLowestAllowed: symbolDetail?.price_lowest_allowed ?? null,
    priceHighestAllowed: symbolDetail?.price_highest_allowed ?? null,
    priceMinWeek: symbolDetail?.price_min_week ?? null,
    priceMaxWeek: symbolDetail?.price_max_week ?? null,
    priceMinYear: symbolDetail?.price_min_year ?? null,
    priceMaxYear: symbolDetail?.price_max_year ?? null,
    priceFirst: symbolDetail?.price_first ?? null,
    priceLastDetail: symbolDetail?.price_last ?? null,
    priceLastChangePct: symbolDetail?.price_last_change_pct ?? null,
    priceCloseChangePct: symbolDetail?.price_close_change_pct ?? null,
    tradeVolumeAvgMonth: symbolDetail?.trade_volume_avg_month ?? null,
    navHistoryPoints: navHistory.length,
    navHistoryFirst,
    navHistoryLast,
    navHistoryChangePct,
    premiumPct,
    spreadPct,
    rangePct,
    analysis: fund.analysis,
    snapshotDate: fund.snapshot_date ?? "",
    navDate: fund.nav_date ?? "",
    updatedAt: fund.updated_at ?? symbolDetail?.updated_at ?? "",
    dataSource: fund.nav_source ?? fund.time ?? "",
    priceLimits: combine(
      symbolDetail?.price_lowest_allowed != null ? text(symbolDetail.price_lowest_allowed) : null,
      symbolDetail?.price_highest_allowed != null ? text(symbolDetail.price_highest_allowed) : null,
    ),
  };
}

function lookupEvidence(item: FundChecklistItem, ctx: ReturnType<typeof buildContext>) {
  const haystack = [item.area, item.subarea, item.title, item.description, item.formula, item.analysis_note, item.source].join(" ").toLowerCase();
  const area = item.area;
  const dimension = areaDimension(area);
  const analysisScore = dimension && ctx.analysis ? ctx.analysis.scores[dimension] : null;

  if (containsAny(haystack, ["نام حقوقی", "نام تجاری", "نماد", "isin", "هویت"])) {
    return {
      value: combine(ctx.symbol, ctx.name, ctx.isin),
      source: "GET /funds/{symbol} + GET /brsapi/symbol-details/{symbol}",
      note: "شناسه و نام از داده واقعی صندوق/نماد",
      availability: "available" as const,
      confidence: 96,
    };
  }

  if (containsAny(haystack, ["بازار", "تابلو", "بخش", "زیرحوزه", "sector"])) {
    return {
      value: combine(ctx.market, ctx.board, ctx.sector, ctx.subSector, ctx.state),
      source: "GET /brsapi/symbol-details/{symbol}",
      note: "ساختار بازار و طبقه‌بندی نماد",
      availability: ctx.market || ctx.sector ? ("available" as const) : ("partial" as const),
      confidence: 88,
    };
  }

  if (containsAny(haystack, ["nav", "خالص ارزش", "ارزش خالص", "nav تاریخچه", "تاریخچه"])) {
    return {
      value: combine(text(ctx.nav), ctx.navDate || ctx.snapshotDate, ctx.navHistoryPoints ? `${ctx.navHistoryPoints} نقطه` : null),
      source: "GET /funds/{symbol}",
      note: "NAV و تاریخچه واقعی صندوق",
      availability: ctx.nav > 0 ? ("available" as const) : ("partial" as const),
      confidence: 98,
    };
  }

  if (containsAny(haystack, ["قیمت", "پایانی", "آخرین", "دیروز", "بازه", "محدود"])) {
    return {
      value: combine(text(ctx.priceLast), text(ctx.priceClose), text(ctx.priceYesterday), `${text(ctx.priceMin)} - ${text(ctx.priceMax)}`),
      source: "GET /funds/{symbol} + GET /brsapi/symbol-details/{symbol}",
      note: "قیمت و بازه معاملاتی واقعی",
      availability: ctx.priceLast > 0 || ctx.priceClose > 0 ? ("available" as const) : ("partial" as const),
      confidence: 92,
    };
  }

  if (containsAny(haystack, ["حجم", "ارزش معامله", "تعداد معامله", "گردش", "نقدشوندگی"])) {
    return {
      value: combine(text(ctx.tradeCount), money(ctx.tradeVolume), money(ctx.tradeValue), money(ctx.tradeVolumeAvgMonth)),
      source: "GET /funds/{symbol} + GET /brsapi/symbol-details/{symbol}",
      note: "حجم و ارزش معاملات واقعی",
      availability: ctx.tradeVolume > 0 || ctx.tradeCount > 0 ? ("available" as const) : ("partial" as const),
      confidence: 94,
    };
  }

  if (containsAny(haystack, ["واحد", "سهام", "عرضه", "شناور", "free float"])) {
    return {
      value: combine(text(ctx.sharesCount), text(ctx.sharesIssued), text(ctx.baseVolume), ctx.freeFloatPct != null ? pct(ctx.freeFloatPct) : null),
      source: "GET /brsapi/symbol-details/{symbol}",
      note: "عرضه و شناوری واقعی نماد",
      availability: ctx.sharesCount > 0 || ctx.sharesIssued > 0 ? ("available" as const) : ("partial" as const),
      confidence: 90,
    };
  }

  if (containsAny(haystack, ["حقیقی", "حقوقی", "ورود", "خروج", "سرانه"])) {
    return {
      value: combine(
        `خرید حقیقی ${text(ctx.buyRealVolume)}`,
        `فروش حقیقی ${text(ctx.sellRealVolume)}`,
        `خالص حقیقی ${text((ctx.buyRealVolume ?? 0) - (ctx.sellRealVolume ?? 0))}`,
        `خالص حقوقی ${text((ctx.buyLegalVolume ?? 0) - (ctx.sellLegalVolume ?? 0))}`,
      ),
      source: "GET /funds/{symbol}",
      note: "جریان واقعی حقیقی/حقوقی",
      availability: ctx.buyRealVolume > 0 || ctx.sellRealVolume > 0 ? ("available" as const) : ("partial" as const),
      confidence: 94,
    };
  }

  if (containsAny(haystack, ["eps", "p/e", "pe", "p/s", "valuation"])) {
    return {
      value: combine(text(ctx.eps), text(ctx.peRatio), text(ctx.groupPeRatio), text(ctx.psRatio)),
      source: "GET /brsapi/symbol-details/{symbol}",
      note: "ارزش‌گذاری واقعی از دیتابیس نماد",
      availability: ctx.eps != null || ctx.peRatio != null ? ("available" as const) : ("partial" as const),
      confidence: 89,
    };
  }

  if (containsAny(haystack, ["ریسک", "نوسان", "افت", "بحران", "هشدار"])) {
    return {
      value: combine(
        ctx.analysis ? `امتیاز ریسک ${ctx.analysis.scores.risk}` : null,
        ctx.rangePct != null ? `دامنه روز ${ctx.rangePct.toFixed(2)}%` : null,
        ctx.premiumPct != null ? `پریمیوم ${pct(ctx.premiumPct)}` : null,
      ),
      source: "تحلیل واقعی صندوق",
      note: "ریسک از داده واقعی و تحلیل ۶‌بعدی",
      availability: ctx.analysis ? ("available" as const) : ("partial" as const),
      confidence: 90,
    };
  }

  if (containsAny(haystack, ["شفافیت", "گزارش", "تاریخ", "به‌روزرسانی"])) {
    return {
      value: combine(ctx.updatedAt, ctx.snapshotDate, ctx.navDate, ctx.dataSource),
      source: "GET /funds/{symbol} + GET /brsapi/symbol-details/{symbol}",
      note: "آخرین زمان ثبت/به‌روزرسانی داده",
      availability: ctx.updatedAt ? ("available" as const) : ("partial" as const),
      confidence: 85,
    };
  }

  if (containsAny(haystack, ["امتیاز", "score", "تحلیل"])) {
    return {
      value: combine(analysisScore != null ? `امتیاز ${analysisScore}` : null, ctx.analysis?.summary),
      source: "تحلیل واقعی صندوق",
      note: "امتیاز از تحلیل ۶‌بعدی استخراج شده",
      availability: ctx.analysis ? ("available" as const) : ("partial" as const),
      confidence: ctx.analysis ? 92 : 20,
    };
  }

  if (containsAny(haystack, ["هزینه", "کارمزد", "expense", "fee"])) {
    return {
      value: ctx.analysis ? `امتیاز هزینه ${ctx.analysis.scores.cost}` : "—",
      source: "تحلیل واقعی صندوق",
      note: "فیلد مستقیم کارمزد در API فعلی موجود نیست",
      availability: ctx.analysis ? ("partial" as const) : ("missing" as const),
      confidence: ctx.analysis ? 70 : 15,
    };
  }

  const fallbackByArea: Record<string, { value: string; source: string; note: string; availability: FundChecklistRowView["availability"]; confidence: number }> = {
    "هویت، تاریخچه و حاکمیت": {
      value: combine(ctx.symbol, ctx.name, ctx.market, ctx.board, ctx.sector),
      source: "GET /funds/{symbol} + GET /brsapi/symbol-details/{symbol}",
      note: "نمایه هویتی و ساختار ثبت",
      availability: ctx.symbol ? "available" : "partial",
      confidence: 84,
    },
    "ذخایر و گزارش‌های اتستیشن": {
      value: combine(text(ctx.nav), text(ctx.navHistoryPoints), ctx.analysis?.summary),
      source: "GET /funds/{symbol}",
      note: "نمای واقعی NAV و تحلیل وضعیت",
      availability: ctx.nav > 0 ? "available" : "partial",
      confidence: 82,
    },
    "زیرساخت": {
      value: combine(ctx.market, ctx.state, ctx.board, ctx.dataSource),
      source: "GET /brsapi/symbol-details/{symbol}",
      note: "زیرساخت ثبت و تابلو نماد",
      availability: ctx.market ? "partial" : "missing",
      confidence: 58,
    },
    "شبکه‌های بلاک‌چینی": {
      value: combine(ctx.market, ctx.board, ctx.sector, ctx.subSector),
      source: "GET /brsapi/symbol-details/{symbol}",
      note: "معادل‌سازی ساختار بازار به جای شبکه",
      availability: ctx.market ? "partial" : "missing",
      confidence: 52,
    },
    "اقتصاد توکنی و عرضه": {
      value: combine(text(ctx.sharesCount), text(ctx.sharesIssued), text(ctx.baseVolume), ctx.freeFloatPct != null ? pct(ctx.freeFloatPct) : null),
      source: "GET /brsapi/symbol-details/{symbol}",
      note: "عرضه، شناوری و پایه واقعی نماد",
      availability: ctx.sharesCount > 0 ? "available" : "partial",
      confidence: 88,
    },
    "بازار جهانی و پیگ": {
      value: combine(ctx.premiumPct != null ? `پریمیوم ${pct(ctx.premiumPct)}` : null, text(ctx.priceLast), text(ctx.nav), text(ctx.priceMin) + " - " + text(ctx.priceMax)),
      source: "GET /funds/{symbol}",
      note: "نسبت قیمت به NAV و دامنه واقعی",
      availability: ctx.nav > 0 ? "available" : "partial",
      confidence: 94,
    },
    "آنچین آنالیتیکس": {
      value: combine(`خرید حقیقی ${text(ctx.buyRealVolume)}`, `فروش حقیقی ${text(ctx.sellRealVolume)}`, `خالص ${text((ctx.buyRealVolume ?? 0) - (ctx.sellRealVolume ?? 0))}`),
      source: "GET /funds/{symbol}",
      note: "جریان واقعی به‌جای آنچین",
      availability: ctx.buyRealVolume > 0 || ctx.sellRealVolume > 0 ? "available" : "partial",
      confidence: 93,
    },
    "ریسک سیستماتیک و مقررات": {
      value: combine(ctx.analysis ? `ریسک ${ctx.analysis.scores.risk}` : null, ctx.state, ctx.priceLowestAllowed != null && ctx.priceHighestAllowed != null ? `${text(ctx.priceLowestAllowed)} - ${text(ctx.priceHighestAllowed)}` : null),
      source: "تحلیل واقعی صندوق + GET /brsapi/symbol-details/{symbol}",
      note: "ریسک، دامنه مجاز و وضعیت نماد",
      availability: ctx.analysis ? "available" : "partial",
      confidence: 88,
    },
    "بازار تتر در ایران": {
      value: combine(text(ctx.tradeVolume), money(ctx.tradeValue), money(ctx.marketValue), text(ctx.tradeCount)),
      source: "GET /funds/{symbol}",
      note: "بازار/گردش واقعی صندوق",
      availability: ctx.tradeVolume > 0 ? "available" : "partial",
      confidence: 90,
    },
    "هشدار سریع و بحران": {
      value: combine(ctx.analysis ? ctx.analysis.summary : null, ctx.updatedAt, ctx.analysis ? `امتیاز کل ${ctx.analysis.scores.total}` : null),
      source: "تحلیل واقعی صندوق",
      note: "هشدار از داده واقعی و تحلیل ۶‌بعدی",
      availability: ctx.analysis ? "available" : "partial",
      confidence: 86,
    },
  };

  const fallback = fallbackByArea[area] ?? {
    value: combine(ctx.symbol, ctx.name, ctx.market),
    source: "GET /funds/{symbol}",
    note: "داده پایه واقعی صندوق",
    availability: "partial" as const,
    confidence: 55,
  };

  return fallback;
}

export function buildFundChecklistRows(
  fund: FundChecklistFundLike,
  symbolDetail?: FundChecklistSymbolDetailLike | null,
): FundChecklistRowView[] {
  const ctx = buildContext(fund, symbolDetail);
  return FUND_CHECKLIST_ITEMS.map((item) => {
    const evidence = lookupEvidence(item, ctx);
    const metadataScore = scoreChecklistItem(item);
    const evidenceScore = scoreForAvailability(evidence.availability, evidence.confidence);
    const score = Math.round(metadataScore * 0.35 + evidenceScore * 0.65);
    return {
      item,
      score,
      importanceLabel: normalizeChecklistImportance(item.importance),
      statusLabel: normalizeChecklistStatus(item.status),
      realValue: evidence.value,
      realSource: evidence.source,
      realNote: evidence.note,
      availability: evidence.availability,
      confidence: evidence.confidence,
    };
  });
}

export function summarizeFundChecklistRows(rows: FundChecklistRowView[]): FundChecklistSummary {
  const averageScore = rows.length ? Math.round(rows.reduce((sum, row) => sum + row.score, 0) / rows.length) : 0;
  return {
    totalItems: rows.length,
    availableCount: rows.filter((row) => row.availability === "available").length,
    partialCount: rows.filter((row) => row.availability === "partial").length,
    missingCount: rows.filter((row) => row.availability === "missing").length,
    averageScore,
  };
}

export function summarizeFundChecklistAreas(rows: FundChecklistRowView[]): FundChecklistAreaSummary[] {
  const groups = new Map<string, FundChecklistRowView[]>();
  for (const row of rows) {
    if (!groups.has(row.item.area)) groups.set(row.item.area, []);
    groups.get(row.item.area)!.push(row);
  }

  return Array.from(groups.entries()).map(([area, items]) => ({
    area,
    itemCount: items.length,
    availableCount: items.filter((row) => row.availability === "available").length,
    partialCount: items.filter((row) => row.availability === "partial").length,
    missingCount: items.filter((row) => row.availability === "missing").length,
    averageScore: items.length ? Math.round(items.reduce((sum, row) => sum + row.score, 0) / items.length) : 0,
  }));
}

export { FUND_CHECKLIST_AREA_ORDER };
