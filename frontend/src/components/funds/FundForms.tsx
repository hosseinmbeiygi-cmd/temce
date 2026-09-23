"use client";

/**
 * Declarative write-panel engine for the funds workspace.
 *
 * Every field below is transcribed from the Pydantic request models in
 * `apps/api/endpoints/funds_{nav,ledger,compliance}.py` — names, defaults and
 * validation bounds (gt/ge/min_length) are mirrored so the browser rejects
 * what the server would reject. Enum options come from label maps that already
 * exist in `lib/fund-*`, never from invented values.
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronDown, Loader2, Send } from "lucide-react";
import { apiPatch, apiPost, apiPut } from "@/lib/api";
import { fundIdOf } from "@/lib/fund-queries";
import { TAX_TYPE_LABELS, COMMITTEE_LABELS } from "@/lib/fund-compliance";
import { MOVEMENT_TYPE_LABELS } from "@/lib/fund-ledger";
import { BREAK_LIFECYCLE_LABELS } from "@/lib/fund-nav";

// ── Contract ────────────────────────────────────────────────────────────────

export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "select" | "textarea" | "checkbox" | "json";
  options?: string[];
  optionLabels?: Record<string, string>;
  required?: boolean;
  default?: string | number | boolean;
  min?: number;
  max?: number;
  step?: number;
  hint?: string;
  placeholder?: string;
  /** Consumed by the URL path, so it is never sent in the body. */
  pathParam?: boolean;
}

export interface ActionSpec {
  id: string;
  title: string;
  desc?: string;
  method: "POST" | "PUT" | "PATCH";
  /** `{fid}` is replaced with the canonical fund id; `{symbol}` with the raw symbol. */
  path: string;
  fields: FieldDef[];
  /** When set, the submit button requires a second confirming click. */
  confirm?: string;
  /** Query-key prefixes invalidated after a successful write. */
  invalidate?: string[];
  /** Endpoints that are market-wide and do not take a fund id. */
  global?: boolean;
}

const NAV_TYPES = ["STATISTICAL", "ISSUANCE", "REDEMPTION"];
const MODES = ["SHADOW", "LIVE"];
const ALLOCATION_TYPES = ["SIMPLE", "LEVERAGED", "GUARANTEED", "FOF"];

// ── Registry ────────────────────────────────────────────────────────────────

export const FUND_ACTIONS: Record<string, ActionSpec[]> = {
  nav: [
    {
      id: "nav-calculate",
      title: "اجرای محاسبه NAV مستقل",
      desc: "خروجی نسخه‌دار و امضاشده برای تاریخ خواسته‌شده؛ حالت SHADOW روی تابلو اثر نمی‌گذارد.",
      method: "POST",
      path: "/funds/v2/nav/{fid}/calculate",
      invalidate: ["funds"],
      fields: [
        { name: "nav_type", label: "نوع NAV", type: "select", options: NAV_TYPES, default: "STATISTICAL" },
        { name: "as_of", label: "تاریخ (YYYY-MM-DD)", type: "date", hint: "خالی = آخرین روز موجود" },
        { name: "mode", label: "حالت اجرا", type: "select", options: MODES, default: "SHADOW" },
      ],
    },
    {
      id: "nav-reconcile",
      title: "اجرای تطبیق با مرجع",
      desc: "NAV داخلی را با NAV منتشرشده مقایسه و در صورت نیاز پرونده مغایرت باز می‌کند.",
      method: "POST",
      path: "/funds/v2/nav/{fid}/reconcile",
      invalidate: ["funds"],
      fields: [
        { name: "nav_type", label: "نوع NAV", type: "select", options: NAV_TYPES, default: "STATISTICAL" },
        { name: "as_of", label: "تاریخ (YYYY-MM-DD)", type: "date" },
        { name: "run_id", label: "شناسه اجرا", type: "number", hint: "خالی = آخرین اجرا" },
        { name: "mode", label: "حالت", type: "select", options: MODES, default: "SHADOW" },
      ],
    },
    {
      id: "nav-break",
      title: "تغییر وضعیت پرونده مغایرت",
      desc: "چرخه عمر پرونده را حرکت می‌دهد؛ برای حسابرسی، «مسئول» را پر کنید.",
      method: "PATCH",
      path: "/funds/v2/nav/breaks/{breakId}",
      confirm: "وضعیت پرونده مغایرت ثبت و در ممیزی نوشته می‌شود",
      invalidate: ["funds"],
      fields: [
        { name: "breakId", label: "شناسه پرونده", type: "number", required: true, pathParam: true },
        { name: "lifecycle", label: "وضعیت جدید", type: "select", required: true, options: Object.keys(BREAK_LIFECYCLE_LABELS), optionLabels: BREAK_LIFECYCLE_LABELS },
        { name: "owner", label: "مسئول", placeholder: "نقش یا نام کاربر" },
        { name: "notes", label: "یادداشت", type: "textarea" },
      ],
    },
    {
      id: "nav-backfill",
      title: "بازسازی تاریخچه NAV",
      desc: "از گزارش‌های دوره، نقاط NAV تاریخی را می‌سازد (برای صندوق‌های تازه کشف‌شده).",
      method: "POST",
      path: "/funds/v2/nav/{fid}/backfill",
      invalidate: ["funds"],
      fields: [
        { name: "days", label: "تعداد روز", type: "number", default: 90, min: 1, max: 1000, required: true },
        { name: "nav_type", label: "نوع NAV", type: "select", options: NAV_TYPES, default: "STATISTICAL" },
      ],
    },
    {
      id: "nav-calibrate",
      title: "کالیبراسیون آستانه تطبیق",
      desc: "آستانه‌های انحراف را از تاریخچه همان نماد بازمحاسبه می‌کند.",
      method: "POST",
      path: "/funds/v2/nav/{fid}/thresholds/calibrate",
      confirm: "آستانه‌های این نماد تغییر می‌کند",
      invalidate: ["funds"],
      fields: [
        { name: "nav_type", label: "نوع NAV", type: "select", options: NAV_TYPES, default: "STATISTICAL" },
        { name: "min_samples", label: "حداقل نمونه", type: "number", default: 10, min: 3, max: 500 },
      ],
    },
    {
      id: "class-config",
      title: "ثبت پیکربندی طبقات (PUT)",
      desc: "نسخه‌دار و از اساسنامه؛ `classes` آرایه‌ای از اشیاء با `class_code` و `allocation_type` است.",
      method: "PUT",
      path: "/funds/v2/nav/{fid}/class-nav/config",
      confirm: "پیکربندی طبقات جایگزین نسخه فعلی می‌شود",
      invalidate: ["funds"],
      fields: [
        { name: "version", label: "نسخه پیکربندی", required: true, placeholder: "مثلاً ۱.۲" },
        {
          name: "classes",
          label: "طبقات (JSON)",
          type: "json",
          required: true,
          hint: `allocation_type ∈ ${ALLOCATION_TYPES.join(" | ")}`,
          default: '[{"class_code":"A","allocation_type":"SIMPLE","weight_pct":100}]',
        },
        { name: "source_document_id", label: "مرجع سند (اساسنامه)" },
      ],
    },
    {
      id: "class-calc",
      title: "محاسبه تخصیص NAV طبقاتی",
      method: "POST",
      path: "/funds/v2/nav/{fid}/class-nav/calculate",
      invalidate: ["funds"],
      fields: [{ name: "valuation_date", label: "تاریخ ارزش‌گذاری", type: "date" }],
    },
    {
      id: "fof-calc",
      title: "محاسبه ارزش فراصندوق",
      desc: "از NAV زیرصندوق‌ها ساخته و حلقه‌های مرجع‌دهی را گزارش می‌کند.",
      method: "POST",
      path: "/funds/v2/nav/{fid}/fof/calculate",
      invalidate: ["funds"],
      fields: [{ name: "valuation_date", label: "تاریخ ارزش‌گذاری", type: "date" }],
    },
  ],

  ledger: [
    {
      id: "unit-movement",
      title: "ثبت حرکت واحد + سند دوطرفه",
      desc: "صدور/ابطال/توزیع سود/انتقال/توثیق/آزادسازی — به‌ازای هر حرکت، سند حسابداری هم ساخته می‌شود.",
      method: "POST",
      path: "/funds/v2/ledger/{fid}/unit-movements",
      confirm: "سند مالی دوطرفه ثبت و قابل حذف نخواهد بود",
      invalidate: ["funds"],
      fields: [
        { name: "movement_type", label: "نوع حرکت", type: "select", required: true, options: Object.keys(MOVEMENT_TYPE_LABELS), optionLabels: MOVEMENT_TYPE_LABELS },
        { name: "movement_date", label: "تاریخ حرکت", type: "date", required: true },
        { name: "units", label: "تعداد واحد", type: "number", required: true, min: 0.000001, step: 1 },
        { name: "price_per_unit", label: "قیمت هر واحد", type: "number", min: 0 },
        { name: "nav_type", label: "نوع NAV", type: "select", options: NAV_TYPES },
        { name: "reference", label: "شماره مرجه" },
      ],
    },
    {
      id: "entry-reverse",
      title: "ثبت سند برگشتی",
      desc: "به‌جای حذف، سند مقابلی ثبت می‌شود (اصول دفتر دوطرفه).",
      method: "POST",
      path: "/funds/v2/ledger/entries/{entryId}/reverse",
      confirm: "سند برگشتی روی سند قبلی ثبت می‌شود",
      invalidate: ["funds"],
      fields: [
        { name: "entryId", label: "شناسه سند", type: "number", required: true, pathParam: true },
        { name: "memo", label: "شرح برگشت", type: "textarea" },
      ],
    },
  ],

  compliance: [
    {
      id: "rpt",
      title: "ثبت معامله با شخص وابسته",
      desc: "مهم‌ترین منبع تشخیص تعارض منافع؛ «افشاشده» را بر اساس اطلاعیه کدال علامت بزنید.",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/rpt",
      invalidate: ["funds"],
      fields: [
        { name: "counterparty", label: "طرف وابسته", required: true },
        { name: "transaction_date", label: "تاریخ معامله", type: "date", required: true },
        { name: "amount", label: "مبلغ", type: "number", min: 0 },
        { name: "relation_type", label: "نوع رابطه", hint: "مثلاً مدیر / عضو هیئت / سهامدار عمده / امین" },
        { name: "approved_by", label: "تأییدکننده" },
        { name: "disclosed", label: "افشا شده است", type: "checkbox" },
        { name: "notes", label: "یادداشت", type: "textarea" },
      ],
    },
    {
      id: "complaint",
      title: "ثبت شکایت",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/complaints",
      invalidate: ["funds"],
      fields: [
        { name: "subject", label: "موضوع", required: true },
        { name: "channel", label: "کانال", default: "SETA", hint: "پیش‌فرض سامانه SETA" },
        { name: "tracking_code", label: "کد پیگیری" },
        { name: "notes", label: "شرح", type: "textarea" },
      ],
    },
    {
      id: "lifecycle",
      title: "ثبت رویداد چرخه عمر",
      desc: "تأسیس، افزایش سرمایه، ادغام، انحلال و تغییرات مجاز — روی تاریخچه سیگنال اثر می‌گذارد.",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/lifecycle",
      invalidate: ["funds"],
      fields: [
        { name: "event_type", label: "نوع رویداد", required: true, hint: "مثلاً CAPITAL_INCREASE / MERGER / LIQUIDATION" },
        { name: "event_date", label: "تاریخ رویداد", type: "date", required: true },
        { name: "details", label: "جزئیات (JSON)", type: "json" },
        { name: "source_ref", label: "مرجع (شماره اطلاعیه)" },
      ],
    },
    {
      id: "prospectus",
      title: "ثبت نسخه اساسنامه",
      desc: "مبنای پارامترهای محاسبه NAV و طبقات؛ هر تغییر باید نسخه جدید بگیرد.",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/prospectus",
      invalidate: ["funds"],
      fields: [
        { name: "version", label: "نسخه", required: true },
        { name: "change_type", label: "نوع تغییر", required: true },
        { name: "changes", label: "محتوای تغییرات (JSON)", type: "json" },
        { name: "assembly_date", label: "تاریخ تصویب مجمع", type: "date" },
        { name: "source_ref", label: "مرجع" },
      ],
    },
    {
      id: "sharia",
      title: "ثبت تأیید شرعی ابزار",
      global: true,
      method: "POST",
      path: "/funds/v2/compliance/sharia/approvals",
      invalidate: ["funds"],
      fields: [
        { name: "approval_ref", label: "شماره تأیید", required: true },
        { name: "instrument_symbol", label: "نماد ابزار" },
        { name: "instrument_type", label: "نوع ابزار" },
        { name: "status", label: "وضعیت", type: "select", options: ["APPROVED", "REJECTED", "EXPIRED"], default: "APPROVED" },
        { name: "notes", label: "یادداشت", type: "textarea" },
      ],
    },
  ],

  aml: [
    {
      id: "aml-generate",
      title: "تولید هشدار AML از حرکت نقدی",
      desc: "حرکت‌های نقدی بالای آستانه را اسکن و هشدار می‌سازد.",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/aml/alerts/generate",
      invalidate: ["funds"],
      fields: [
        { name: "cash_threshold", label: "آستانه نقدی (ریال)", type: "number", min: 1, default: 1_000_000_000, hint: "پیش‌فرض ۱ میلیارد ریال — پارامتریک" },
      ],
    },
    {
      id: "aml-str",
      title: "ایجاد گزارش معامله مشکوک (STR)",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/aml/str",
      confirm: "STR ثبت می‌شود و قابل ارسال به واحد اطلاعات مالی خواهد بود",
      invalidate: ["funds"],
      fields: [
        { name: "reason", label: "دلیل", required: true, min: 3, max: 300, type: "textarea", hint: "بین ۳ تا ۳۰۰ نویسه" },
        { name: "alert_id", label: "شناسه هشدار مبدأ", type: "number" },
        { name: "subject_ref", label: "مرجع موضوع" },
        { name: "amount", label: "مبلغ", type: "number", min: 0 },
      ],
    },
  ],

  tax: [
    {
      id: "tax-calculate",
      title: "محاسبه و ثبت مالیات",
      desc: "نرخ از قواعد نسخه‌دار مالیاتی خوانده می‌شود، نه از ورودی کاربر.",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/tax/calculate",
      invalidate: ["funds"],
      fields: [
        { name: "tax_type", label: "نوع مالیات", type: "select", required: true, options: Object.keys(TAX_TYPE_LABELS), optionLabels: TAX_TYPE_LABELS },
        { name: "base_amount", label: "مبنای محاسبه", type: "number", required: true, min: 0 },
        { name: "period_label", label: "برچسب دوره", required: true, hint: "مثلاً ۱۴۰-۰۶" },
      ],
    },
    {
      id: "tax-trades",
      title: "مالیات مقطوع از جریان معاملات",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/tax/from-trades",
      invalidate: ["funds"],
      fields: [
        { name: "period_label", label: "برچسب دوره", required: true },
        { name: "trades", label: "معاملات (JSON)", type: "json", required: true, hint: "آرایه‌ای با حداقل یک عنصر", default: '[{"symbol":"","side":"BUY","price":0,"volume":0}]' },
      ],
    },
  ],

  governance: [
    {
      id: "committee",
      title: "ثبت کمیته حاکمیتی",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/committees",
      invalidate: ["funds"],
      fields: [
        { name: "committee_type", label: "نوع کمیته", type: "select", required: true, options: Object.keys(COMMITTEE_LABELS), optionLabels: COMMITTEE_LABELS },
        { name: "members", label: "اعضا (JSON)", type: "json" },
        { name: "charter_ref", label: "مرجع منشور" },
        { name: "formed_at", label: "تاریخ تشکیل", type: "date" },
      ],
    },
    {
      id: "internal-audit",
      title: "ثبت گزارش حسابرسی داخلی",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/internal-audits",
      invalidate: ["funds"],
      fields: [
        { name: "period_label", label: "دوره", required: true },
        { name: "report_date", label: "تاریخ گزارش", type: "date" },
        { name: "findings", label: "یافته‌ها (JSON)", type: "json" },
      ],
    },
    {
      id: "disciplinary",
      title: "ثبت پرونده انتظامی",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/disciplinary",
      invalidate: ["funds"],
      fields: [
        { name: "subject_role", label: "نقش مشمول", required: true },
        { name: "case_type", label: "نوع تخلف", required: true },
        { name: "subject_name", label: "نام" },
        { name: "notes", label: "شرح", type: "textarea" },
      ],
    },
    {
      id: "insurance",
      title: "ثبت بیمه‌نامه مسئولیت",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/insurance",
      invalidate: ["funds"],
      fields: [
        { name: "policy_type", label: "نوع بیمه", default: "D_AND_O" },
        { name: "insurer", label: "بیمه‌گر" },
        { name: "coverage_amount", label: "تضمین", type: "number", min: 0 },
        { name: "valid_from", label: "اعتبار از", type: "date" },
        { name: "valid_to", label: "اعتبار تا", type: "date" },
        { name: "policy_ref", label: "شماره بیمه‌نامه" },
      ],
    },
  ],

  csdi: [
    {
      id: "csdi-statement",
      title: "ورود صورت‌وضعیت واحدها از CSDI",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/csdi/statements",
      invalidate: ["funds"],
      fields: [
        { name: "as_of_date", label: "تاریخ صورت‌وضعیت", type: "date", required: true },
        { name: "units_outstanding", label: "واحدهای معادل CSDI", type: "number", required: true, min: 0, step: 1 },
        { name: "source_ref", label: "مرجع/شماره صورت‌وضعیت", required: true },
        { name: "payload", label: "متن اصلی (JSON)", type: "json" },
      ],
    },
    {
      id: "csdi-reconcile",
      title: "تطبیق واحدها با CSDI",
      desc: "مغایرت تعداد واحدهای داخلی با آخرین صورت‌وضعیت را محاسبه می‌کند.",
      method: "POST",
      path: "/funds/v2/compliance/{fid}/csdi/reconcile",
      invalidate: ["funds"],
      fields: [],
    },
  ],

  market: [
    {
      id: "discover",
      title: "اجرای کشف کامل Universe",
      global: true,
      desc: "صندوق جدید بدون تغییر کد شناسایی می‌شود؛ خطای یک صندوق بقیه را متوقف نمی‌کند.",
      method: "POST",
      path: "/funds/v2/discover",
      invalidate: ["funds"],
      fields: [
        { name: "market", label: "بازار", type: "select", options: ["tse", "ime"] },
        { name: "limit", label: "حداکثر", type: "number", min: 1, max: 2000, default: 500 },
      ],
    },
    {
      id: "sync-all",
      title: "همگام‌سازی انبوه از اسنپ‌شات BrsApi",
      global: true,
      method: "POST",
      path: "/funds/sync-all",
      invalidate: ["funds"],
      fields: [{ name: "limit", label: "تعداد صندوق", type: "number", min: 20, max: 80, default: 20 }],
    },
  ],
};

// ── Engine ──────────────────────────────────────────────────────────────────

type Values = Record<string, string | number | boolean>;

function initial(spec: ActionSpec): Values {
  const v: Values = {};
  for (const f of spec.fields) v[f.name] = f.default ?? (f.type === "checkbox" ? false : "");
  return v;
}

function validate(spec: ActionSpec, values: Values): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const f of spec.fields) {
    const raw = values[f.name];
    const empty = raw === "" || raw === null || raw === undefined;
    if (f.required && empty) {
      errors[f.name] = "این فیلد لازم است";
      continue;
    }
    if (empty) continue;
    if (f.type === "number") {
      const n = Number(raw);
      if (!Number.isFinite(n)) errors[f.name] = "عدد معتبر نیست";
      else if (f.min !== undefined && n < f.min) errors[f.name] = `نباید کمتر از ${f.min} باشد`;
      else if (f.max !== undefined && n > f.max) errors[f.name] = `نباید بیشتر از ${f.max} باشد`;
    }
    if (f.type === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(String(raw))) errors[f.name] = "قالب تاریخ YYYY-MM-DD است";
    if (f.type === "json") {
      try {
        const parsed = JSON.parse(String(raw));
        if (Array.isArray(parsed) && parsed.length === 0) errors[f.name] = "آرایه خالی مجاز نیست";
      } catch {
        errors[f.name] = "JSON معتبر نیست";
      }
    }
    if (f.type === "textarea" || f.type === "text") {
      const len = String(raw).length;
      if (f.min !== undefined && len < f.min) errors[f.name] = `حداقل ${f.min} نویسه`;
      if (f.max !== undefined && len > f.max) errors[f.name] = `حداکثر ${f.max} نویسه`;
    }
  }
  return errors;
}

function payloadFor(spec: ActionSpec, values: Values): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of spec.fields) {
    const raw = values[f.name];
    if (f.pathParam) continue;
    if (raw === "" || raw === null || raw === undefined) continue;
    if (f.type === "number") out[f.name] = Number(raw);
    else if (f.type === "json") out[f.name] = JSON.parse(String(raw));
    else if (f.type === "checkbox") out[f.name] = Boolean(raw);
    else out[f.name] = raw;
  }
  if (spec.id === "aml-generate" && out.cash_threshold === undefined) out.cash_threshold = 1_000_000_000;
  return out;
}

function resolvePath(spec: ActionSpec, symbol: string, values: Values): string {
  const fid = fundIdOf(symbol);
  let path = spec.path.replace("{fid}", encodeURIComponent(fid)).replace("{symbol}", encodeURIComponent(symbol));
  if (path.includes("{breakId}")) path = path.replace("{breakId}", encodeURIComponent(String(values.breakId ?? "")));
  if (path.includes("{entryId}")) path = path.replace("{entryId}", encodeURIComponent(String(values.entryId ?? "")));
  return path;
}

function ActionCard({ spec, symbol }: { spec: ActionSpec; symbol: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Values>(() => initial(spec));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [armed, setArmed] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const body = payloadFor(spec, values);
      const path = resolvePath(spec, symbol, values);
      const send = spec.method === "PUT" ? apiPut : spec.method === "PATCH" ? apiPatch : apiPost;
      return send<{ success?: boolean; error?: { message?: string }; message?: string }>(path, body);
    },
    onSuccess: (res) => {
      if (res && res.success === false) {
        toast.error(res.error?.message ?? "عملیات ناموفق");
        return;
      }
      toast.success(`${spec.title} انجام شد`);
      for (const key of spec.invalidate ?? ["funds"]) qc.invalidateQueries({ queryKey: [key] });
      setArmed(false);
      setOpen(false);
    },
    onError: (e: unknown) => {
      toast.error(e instanceof Error ? e.message : "ارسال ناموفق");
    },
  });

  function submit() {
    const found = validate(spec, values);
    setErrors(found);
    if (Object.keys(found).length) return;
    if (spec.confirm && !armed) {
      setArmed(true);
      return;
    }
    mutation.mutate();
  }

  const needsSymbol = !spec.global;
  if (needsSymbol && !symbol) return null;

  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-right hover:bg-white/[0.03] transition-colors"
      >
        <span className="min-w-0">
          <span className="block text-xs font-bold text-surface-100">{spec.title}</span>
          {spec.desc && <span className="block text-[10px] text-surface-500 mt-0.5 leading-relaxed">{spec.desc}</span>}
        </span>
        <ChevronDown className={`w-4 h-4 shrink-0 text-surface-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-surface-700/50 pt-3">
          <div className="grid sm:grid-cols-2 gap-3">
            {spec.fields.map((f) => (
              <label key={f.name} className={`block ${f.type === "textarea" || f.type === "json" ? "sm:col-span-2" : ""}`}>
                <span className="block text-[10px] text-surface-500 mb-1">
                  {f.label}
                  {f.required && <span className="text-accent-rose"> *</span>}
                </span>
                {f.type === "select" ? (
                  <select
                    value={String(values[f.name] ?? "")}
                    onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-[11px]"
                  >
                    <option value="">—</option>
                    {f.options?.map((o) => (
                      <option key={o} value={o}>
                        {f.optionLabels?.[o] ?? o}
                      </option>
                    ))}
                  </select>
                ) : f.type === "checkbox" ? (
                  <button
                    type="button"
                    onClick={() => setValues((v) => ({ ...v, [f.name]: !v[f.name] }))}
                    className={`w-full text-[11px] font-bold px-3 py-2 rounded-lg border transition-colors ${
                      values[f.name] ? "bg-accent-emerald/15 border-accent-emerald/40 text-accent-emerald" : "bg-surface-800 border-surface-700 text-surface-400"
                    }`}
                  >
                    {values[f.name] ? "بله" : "خیر"}
                  </button>
                ) : f.type === "textarea" || f.type === "json" ? (
                  <textarea
                    value={String(values[f.name] ?? "")}
                    onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    rows={f.type === "json" ? 4 : 2}
                    dir={f.type === "json" ? "ltr" : undefined}
                    className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-[11px] font-mono"
                  />
                ) : (
                  <input
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                    value={String(values[f.name] ?? "")}
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    placeholder={f.placeholder ?? f.hint}
                    onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    dir="ltr"
                    className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-[11px]"
                  />
                )}
                {f.hint && f.type !== "text" && <span className="block text-[9px] text-surface-600 mt-1">{f.hint}</span>}
                {errors[f.name] && <span className="block text-[9px] text-accent-rose mt-1">{errors[f.name]}</span>}
              </label>
            ))}
          </div>

          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={submit}
              disabled={mutation.isPending}
              className={`inline-flex items-center gap-1.5 text-[11px] font-black px-3 py-2 rounded-lg transition-colors disabled:opacity-60 ${
                armed
                  ? "bg-accent-amber/20 text-accent-amber border border-accent-amber/40"
                  : "bg-primary-600 hover:bg-primary-500 text-white"
              }`}
            >
              {mutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              {mutation.isPending ? "در حال ارسال…" : armed ? spec.confirm : "ارسال"}
            </button>
            {spec.confirm && !armed && <span className="text-[9px] text-surface-600">این عملیات رکورد ثبت می‌کند — با تأیید دوم</span>}
            <code className="text-[9px] text-surface-600 mr-auto" dir="ltr">
              {spec.method} {spec.path}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}

export function ActionGroup({ group, symbol }: { group: string; symbol?: string }) {
  const specs = FUND_ACTIONS[group] ?? [];
  return (
    <div className="space-y-2">
      {specs.map((s) => (
        <ActionCard key={s.id} spec={s} symbol={symbol ?? ""} />
      ))}
    </div>
  );
}

