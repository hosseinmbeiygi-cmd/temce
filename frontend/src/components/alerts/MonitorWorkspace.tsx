"use client";

/**
 * Alert-engine workspace: instruments monitored through the Alerts section.
 *
 * Adding a symbol starts identity verification → data-coverage checks → baseline analysis →
 * continuous monitoring on the server. This panel only displays analysis and lets the user
 * record trades they confirm were executed; it never places an order.
 *
 * Sound: browsers only allow audio after a user gesture and throttle background tabs, so a
 * chime is best-effort and is never reported as "delivered".
 */

import { useCallback, useEffect, useRef, useState } from "react";
import SymbolSelector from "@/components/SymbolSelector";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { describeApiError } from "@/lib/api-errors";
import { useNotificationSound } from "@/hooks/useNotificationSound";

type Dict = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

interface MonitorRow {
  id: string; symbol: string; name: string | null; category_label: string; supported: boolean;
  monitoring_state: string; state: string; state_label: string; reason: string | null;
  last_analyzed_at: string | null; valid_until: string | null; expired: boolean;
  quote_status: string | null; quote_as_of: string | null; price_last: number | null; regime: string | null;
  last_error: string | null;
}
interface Notice {
  id: string; symbol: string | null; severity: string; severity_label: string; title: string; body: string | null;
  created_at: string; valid_until: string | null; acknowledged_at: string | null; revises_id: string | null;
  telegram: { state: string; error: string | null };
}

const TONES: Record<string, number[]> = {
  opportunity: [660, 880],
  material_change: [520, 660],
  risk_warning: [440, 330],
  critical: [880, 440, 880, 440],
};
const STATE_TONE: Record<string, string> = {
  conditional_entry: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  hold: "bg-sky-500/10 text-sky-300 border-sky-500/30",
  await_confirmation: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  reduce: "bg-orange-500/10 text-orange-300 border-orange-500/30",
  exit: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  exit_infeasible: "bg-rose-600/20 text-rose-300 border-rose-500/50",
  insufficient_data: "bg-surface-700 text-gray-300 border-surface-600",
};
const MONITORING_LABEL: Record<string, string> = {
  ok: "پایش عادی", degraded: "پایش با دادهٔ ناقص", blocked: "متوقف: دادهٔ حیاتی ناکافی", pending: "در انتظار",
  unsupported: "پشتیبانی نمی‌شود", restricted: "محدود", error: "خطا در تحلیل",
};
const COVERAGE_TONE: Record<string, string> = {
  valid: "text-emerald-400", last_session: "text-sky-300", stale: "text-amber-300", missing: "text-rose-400",
  invalid: "text-rose-400", unavailable: "text-gray-500", not_applicable: "text-gray-600",
};
const COVERAGE_LABEL: Record<string, string> = {
  valid: "معتبر و تازه", last_session: "آخرین جلسه", stale: "کهنه", missing: "موجود نیست", invalid: "نامعتبر",
  unavailable: "در دسترس نیست", not_applicable: "کاربرد ندارد",
};
const SEVERITY_TONE: Record<string, string> = {
  informational: "border-surface-600", opportunity: "border-emerald-500/50", material_change: "border-amber-500/50",
  risk_warning: "border-orange-500/60", critical: "border-rose-500/70",
};

const num = (v: unknown, digits = 0) =>
  typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("en-US", { maximumFractionDigits: digits }) : "—";
const when = (v: string | null | undefined) => (v ? new Date(v).toLocaleString("fa-IR") : "—");
const data = <T,>(r: unknown): T => (r as { data: T }).data;

export default function MonitorWorkspace() {
  const [monitors, setMonitors] = useState<MonitorRow[]>([]);
  const [portfolio, setPortfolio] = useState<Dict | null>(null);
  const [health, setHealth] = useState<Dict | null>(null);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [settings, setSettings] = useState<Dict | null>(null);
  const [symbol, setSymbol] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Dict | null>(null);
  const [tab, setTab] = useState("summary");
  const [showLedger, setShowLedger] = useState(false);
  const seen = useRef<Set<string> | null>(null);
  const { muted, toggleMute, playChime } = useNotificationSound({ storageKey: "alert-engine-sound-muted" });
  const playChimeRef = useRef(playChime);
  useEffect(() => { playChimeRef.current = playChime; }, [playChime]);

  const refresh = useCallback(async () => {
    try {
      const [m, p, h, n, s] = await Promise.all([
        apiGet("/alerts/monitors"), apiGet("/alerts/engine/portfolio"), apiGet("/alerts/engine/health"),
        apiGet("/alerts/engine/notifications?limit=30"), apiGet("/alerts/engine/settings"),
      ]);
      setMonitors(data<{ items: MonitorRow[] }>(m).items);
      setPortfolio(data<Dict>(p));
      setHealth(data<Dict>(h));
      setSettings(data<Dict>(s));
      const items = data<{ items: Notice[] }>(n).items;
      setNotices(items);
      const audible: string[] = data<Dict>(s).settings.notifications.sound_severities ?? [];
      const soundOn: boolean = data<Dict>(s).settings.notifications.sound_enabled;
      if (seen.current === null) {
        seen.current = new Set(items.map((x) => x.id)); // first load: nothing is "new"
      } else {
        const fresh = items.filter((x) => !seen.current!.has(x.id));
        fresh.forEach((x) => seen.current!.add(x.id));
        const order = ["critical", "risk_warning", "opportunity", "material_change"];
        const top = order.find((sev) => fresh.some((x) => x.severity === sev));
        if (top && soundOn && audible.includes(top)) playChimeRef.current(TONES[top]);
      }
    } catch (err) {
      setError(describeApiError(err, "دریافت وضعیت پایش ناموفق بود."));
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 30_000);
    return () => clearInterval(timer);
  }, [refresh]);

  const loadDetail = useCallback(async (id: string) => {
    try {
      setDetail(data<Dict>(await apiGet(`/alerts/monitors/${id}`)));
    } catch (err) {
      setError(describeApiError(err, "دریافت گزارش ناموفق بود."));
    }
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (err) { setError(describeApiError(err, "عملیات ناموفق بود.")); }
    setBusy(false);
  }

  const addMonitor = () => run(async () => {
    if (!symbol) { setError("یک نماد انتخاب کنید"); return; }
    const res = data<Dict>(await apiPost("/alerts/monitors", { symbol }, undefined, 120_000));
    setMessage(res.created ? `پایش «${res.monitor.symbol}» آغاز شد.` : `«${res.monitor.symbol}» از قبل در پایش است.`);
    setSymbol(""); setOpenId(res.monitor.id); setDetail(res.monitor); setTab("summary");
    await refresh();
  });

  const removeMonitor = (m: MonitorRow) => run(async () => {
    let res = data<Dict>(await apiDelete(`/alerts/monitors/${m.id}`));
    if (res.requires_acknowledgement) {
      if (!window.confirm(res.warning)) return;
      res = data<Dict>(await apiDelete(`/alerts/monitors/${m.id}?acknowledge_position=true`));
    }
    if (res.removed) setMessage(`پایش «${m.symbol}» متوقف شد${res.position_still_recorded ? " — موقعیت ثبت‌شده همچنان باز است" : ""}.`);
    if (openId === m.id) { setOpenId(null); setDetail(null); }
    await refresh();
  });

  const reanalyze = (id: string) => run(async () => {
    setDetail(data<Dict>(await apiPost(`/alerts/monitors/${id}/analyze`)).monitor);
    await refresh();
  });

  const acknowledge = (id?: string) => run(async () => {
    await apiPost("/alerts/engine/notifications/ack", id ? { notification_id: id } : {});
    await refresh();
  });

  const testTelegram = () => run(async () => {
    await apiPost("/alerts/engine/notifications/test-telegram");
    setMessage("پیام آزمایشی توسط تلگرام پذیرفته شد (پذیرش ارائه‌دهنده به معنی دیده‌شدن نیست).");
    await refresh();
  });

  const patchSettings = (patch: Dict, confirmLoosening = false) => run(async () => {
    await apiPut("/alerts/engine/settings", { patch, confirm_loosening: confirmLoosening });
    await refresh();
  });

  const toggle = (m: MonitorRow) => {
    if (openId === m.id) { setOpenId(null); setDetail(null); return; }
    setOpenId(m.id); setDetail(null); setTab("summary"); loadDetail(m.id);
  };

  const prefs = settings?.settings?.notifications;
  const riskSettings = settings?.settings?.risk;
  const unack = notices.filter((n) => !n.acknowledged_at).length;

  return (
    <div className="space-y-5">
      <p className="text-xs text-gray-500 leading-6">
        این بخش فقط تحلیل، توصیهٔ مشروط و اعلان ارائه می‌کند و هیچ سفارشی ثبت، اصلاح یا لغو نمی‌کند. خروجی‌ها در حالت
        «کاغذی» و بر پایهٔ قواعد اعتبارسنجی‌نشده‌اند؛ «بدون معامله» یک نتیجهٔ معتبر است.
      </p>

      {message && <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-4 py-2 rounded-lg text-sm">{message}</div>}
      {error && <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 px-4 py-2 rounded-lg text-sm">{error}</div>}

      {/* ── portfolio strip ── */}
      {portfolio && (
        <div className="glass-card p-4">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-sm">
            <Stat label="سرمایهٔ تخصیصی (تومان)" value={num(portfolio.allocated_capital_toman)} />
            <Stat label="نقد در دسترس" value={num(portfolio.cash_toman)} />
            <Stat label="ارزش پرتفوی" value={num(portfolio.equity_toman)} warn={!portfolio.equity_complete ? "ناقص: قیمت برخی موقعیت‌ها معتبر نیست" : undefined} />
            <Stat label="درگیری سرمایه" value={`${num(portfolio.exposure_pct, 1)}٪`} />
            <Stat label="سود/زیان امروز" value={num(portfolio.daily?.pnl_toman)} warn={portfolio.daily?.loss_breached ? "حد زیان روزانه نقض شده" : undefined} />
            <Stat label="افت از سقف" value={`${num(portfolio.drawdown?.pct, 2)}٪`} warn={portfolio.drawdown?.review_required ? "بازبینی راهبرد لازم است" : undefined} />
          </div>
          <p className="text-[11px] text-gray-500 mt-3">
            بودجهٔ ریسک هر معامله {num(portfolio.budgets_toman?.per_trade_risk)} | توقف زیان روزانه {num(portfolio.daily?.loss_stop_toman)} | آستانهٔ بازبینی افت {num(portfolio.budgets_toman?.drawdown_review)} تومان — مقادیر موقت و قابل تنظیم، نه تضمین سقف زیان. سرمایه بین همهٔ ابزارها مشترک است.
          </p>
          {portfolio.blocked_new_entries?.length > 0 && (
            <p className="text-xs text-rose-300 mt-2">توصیهٔ ورود جدید متوقف است: {portfolio.blocked_new_entries.join("؛ ")}</p>
          )}
          {portfolio.recommendations?.relationship === "competing_for_same_cash" && (
            <p className="text-xs text-amber-300 mt-2">توصیه‌های ورود فعلی برای یک نقدینگی رقابت می‌کنند ({num(portfolio.recommendations.requested_toman)} تومان درخواست در برابر {num(portfolio.cash_toman)} نقد).</p>
          )}
          <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
            <button onClick={() => setShowLedger((v) => !v)} className="px-2 py-1 rounded-lg bg-surface-800 border border-surface-700 text-gray-300">
              {showLedger ? "بستن ثبت معامله" : "ثبت معامله/واریز تأییدشده"}
            </button>
            {riskSettings && (
              <button
                onClick={() => patchSettings({ risk: { halt_new_entries: !riskSettings.halt_new_entries } }, riskSettings.halt_new_entries)}
                className={`px-2 py-1 rounded-lg border ${riskSettings.halt_new_entries ? "bg-rose-500/20 border-rose-500/40 text-rose-300" : "bg-surface-800 border-surface-700 text-gray-300"}`}
                title="فقط توصیه‌های افزایش ریسک را متوقف می‌کند؛ نمایش موقعیت‌ها و هشدارهای ریسک ادامه دارد"
              >
                {riskSettings.halt_new_entries ? "ازسرگیری توصیهٔ ورود" : "توقف توصیهٔ ورود جدید"}
              </button>
            )}
            <span className="text-gray-600">نسخهٔ تنظیمات: {portfolio.settings_version}</span>
          </div>
          {showLedger && <LedgerForm onDone={async () => { setShowLedger(false); await refresh(); }} onError={setError} />}
          {portfolio.positions?.length > 0 && (
            <table className="w-full text-xs mt-3">
              <thead><tr className="text-gray-500"><th className="text-right py-1">موقعیت تأییدشده</th><th>تعداد</th><th>میانگین خرید (تومان)</th><th>ارزش (تومان)</th><th>وزن</th><th>سود/زیان باز</th></tr></thead>
              <tbody>{portfolio.positions.map((p: Dict) => (
                <tr key={p.symbol} className="text-center border-t border-surface-700/40">
                  <td className="text-right py-1">{p.symbol}{!p.marked && <span className="text-amber-300"> (بدون قیمت معتبر)</span>}</td>
                  <td>{num(p.quantity)}</td><td>{num(p.avg_cost_toman, 1)}</td><td>{num(p.value_toman)}</td><td>{num(p.weight_pct, 1)}٪</td><td>{num(p.unrealized_pnl_toman)}</td>
                </tr>))}</tbody>
            </table>
          )}
        </div>
      )}

      {/* ── health + sound + telegram ── */}
      <div className="glass-card p-4 text-xs flex flex-wrap items-center gap-x-5 gap-y-2">
        <span>دادهٔ بازار: <b className={COVERAGE_TONE[health?.market_data?.status] ?? ""}>{COVERAGE_LABEL[health?.market_data?.status] ?? "—"}</b> <span className="text-gray-500">({when(health?.market_data?.as_of)})</span></span>
        <span>بازار: {health?.market_open ? "باز" : "بسته"}</span>
        <button onClick={toggleMute} className="px-2 py-1 rounded-lg bg-surface-800 border border-surface-700">{muted ? "🔕 صدا خاموش" : "🔊 صدا روشن"}</button>
        <button onClick={() => playChime(TONES.risk_warning)} className="px-2 py-1 rounded-lg bg-surface-800 border border-surface-700">آزمایش صدا</button>
        {prefs && (
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={prefs.telegram_enabled} onChange={(e) => patchSettings({ notifications: { telegram_enabled: e.target.checked } })} /> تلگرام
          </label>
        )}
        <button onClick={testTelegram} disabled={busy} className="px-2 py-1 rounded-lg bg-surface-800 border border-surface-700">آزمایش اتصال تلگرام</button>
        <span className="text-gray-500">
          ربات: {health?.telegram?.bot_configured ? "پیکربندی شده" : "پیکربندی نشده"} | گفتگو: {health?.telegram?.chat_linked ? "متصل" : "متصل نیست"}
        </span>
        <span className="text-gray-600 basis-full">پخش صدا به اجازهٔ مرورگر (یک کلیک در صفحه) نیاز دارد و در زبانهٔ پس‌زمینه یا بسته تضمین نمی‌شود.</span>
      </div>

      {/* ── add ── */}
      <div className="glass-card p-4 flex items-start gap-2">
        <div className="flex-1"><SymbolSelector value={symbol} onChange={setSymbol} placeholder="افزودن ابزار به پایش..." /></div>
        <button onClick={addMonitor} disabled={busy} className="bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm">
          {busy ? "..." : "افزودن به پایش"}
        </button>
      </div>

      {/* ── monitors ── */}
      {monitors.length === 0 ? (
        <div className="glass-card p-8 text-center text-gray-500 text-sm">هنوز ابزاری در پایش نیست. افزودن ابزار به معنی خرید یا تخصیص سرمایه نیست.</div>
      ) : monitors.map((m) => (
        <div key={m.id} className="glass-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button className="text-right flex-1 min-w-[220px]" onClick={() => toggle(m)}>
              <p className="font-medium">{m.symbol} <span className="text-xs text-gray-500">{m.name} — {m.category_label}</span></p>
              <p className="text-xs text-gray-400 mt-1">{m.reason ?? m.last_error ?? "—"}</p>
              <p className="text-[11px] text-gray-500 mt-1">
                {MONITORING_LABEL[m.monitoring_state] ?? m.monitoring_state} | قیمت: <span className={COVERAGE_TONE[m.quote_status ?? ""] ?? ""}>{COVERAGE_LABEL[m.quote_status ?? ""] ?? "—"}</span> ({when(m.quote_as_of)}) | آخرین تحلیل: {when(m.last_analyzed_at)} | اعتبار تا: {when(m.valid_until)}{m.expired ? " (منقضی)" : ""}
              </p>
            </button>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded-full border ${STATE_TONE[m.state] ?? "bg-surface-700 text-gray-300 border-surface-600"}`}>{m.state_label}</span>
              <button onClick={() => reanalyze(m.id)} disabled={busy} className="text-xs px-2 py-1 rounded-lg bg-primary-600/10 text-primary-300">تحلیل مجدد</button>
              <button onClick={() => removeMonitor(m)} disabled={busy} className="text-xs text-rose-400">حذف</button>
            </div>
          </div>
          {openId === m.id && (detail ? <Detail d={detail} tab={tab} setTab={setTab} /> : <p className="text-xs text-gray-500 mt-3">در حال دریافت گزارش…</p>)}
        </div>
      ))}

      {/* ── notifications ── */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">اعلان‌ها {unack > 0 && <span className="text-xs text-amber-300">({unack} تأییدنشده)</span>}</h3>
          {unack > 0 && <button onClick={() => acknowledge()} className="text-xs text-primary-300">تأیید همه</button>}
        </div>
        {notices.length === 0 ? <p className="text-xs text-gray-500">اعلانی ثبت نشده است.</p> : (
          <div className="space-y-1.5">
            {notices.map((n) => (
              <div key={n.id} className={`text-xs border-r-2 pr-2 py-1 ${SEVERITY_TONE[n.severity] ?? ""} ${n.acknowledged_at ? "opacity-60" : ""}`}>
                <div className="flex justify-between gap-2">
                  <span><b>{n.severity_label}</b> — {n.title}{n.revises_id ? " ↩" : ""}</span>
                  {!n.acknowledged_at && <button onClick={() => acknowledge(n.id)} className="text-primary-300 whitespace-nowrap">دیدم</button>}
                </div>
                {n.body && <p className="text-gray-400 whitespace-pre-line">{n.body}</p>}
                <p className="text-gray-600">{when(n.created_at)} | درون‌برنامه: ثبت شد | تلگرام: {n.telegram.state}{n.telegram.error ? ` (${n.telegram.error})` : ""}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value: string; warn?: string }) {
  return (
    <div>
      <p className="text-[11px] text-gray-500">{label}</p>
      <p className="font-mono">{value}</p>
      {warn && <p className="text-[10px] text-rose-300">{warn}</p>}
    </div>
  );
}

function List({ title, items, tone = "text-gray-300" }: { title: string; items: unknown[]; tone?: string }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className="text-[11px] text-gray-500 mb-1">{title}</p>
      <ul className={`text-xs space-y-0.5 list-disc pr-4 ${tone}`}>
        {items.map((x, i) => <li key={i}>{typeof x === "string" ? x : (x as Dict).text}</li>)}
      </ul>
    </div>
  );
}

const TABS: [string, string][] = [
  ["summary", "نتیجه"], ["data", "پوشش داده"], ["market", "بازار و نقدشوندگی"], ["options", "اختیارهای مرتبط"],
  ["nav", "NAV / ارزش‌گذاری"], ["events", "افشاها"], ["history", "تاریخچه"],
];

function Detail({ d, tab, setTab }: { d: Dict; tab: string; setTab: (t: string) => void }) {
  const report: Dict | null = d.report;
  if (!report) return <p className="text-xs text-gray-500 mt-3">هنوز تحلیلی ثبت نشده است.</p>;
  const rec: Dict = report.recommendation;
  const m: Dict | null = report.market;
  const opt: Dict = report.options ?? {};
  return (
    <div className="mt-4 pt-3 border-t border-surface-700/50">
      <div className="flex flex-wrap gap-1 mb-3">
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={`text-xs px-2 py-1 rounded-lg ${tab === key ? "bg-primary-600 text-white" : "bg-surface-800 text-gray-400"}`}>{label}</button>
        ))}
      </div>

      {tab === "summary" && (
        <div className="space-y-3">
          <p className="text-sm"><b>{rec.state_label}</b> <span className="text-xs text-gray-500">— {rec.subject === "confirmed_position" ? "موقعیت تأییدشده" : "موقعیت جدید (فرضی)"} | حالت {rec.mode} | قواعد {rec.rules_version} | رژیم بازار (آزمایشی): {rec.regime}</span></p>
          <List title="دلیل" items={rec.reasons} />
          <List title="شرایط فعال‌سازی" items={rec.activation_conditions} tone="text-amber-200" />
          <List title="شرایط ابطال" items={rec.invalidation_conditions} tone="text-rose-200" />
          {rec.entry && (
            <p className="text-xs text-gray-300">
              قیمت قابل اجرای برآوردی {num(rec.entry.estimated_executable_price_rial)} ریال | حد ضرر تحلیلی {num(rec.entry.analytical_stop_rial)} | تعداد {num(rec.entry.units)} | ارزش {num(rec.entry.value_toman)} تومان | زیان برنامه‌ای {num(rec.entry.planned_loss_toman)} تومان | محدودیت تعیین‌کننده: {rec.entry.binding_constraint} | هزینهٔ رفت‌وبرگشت {num(rec.entry.round_trip_cost_pct, 2)}٪
            </p>
          )}
          {rec.exit_assessment && (
            <div className="text-xs text-gray-300">
              <p>ارزیابی خروج ({rec.exit_assessment.class}): {rec.exit_assessment.label} — {rec.exit_assessment.note}</p>
              {rec.exit_assessment.overnight?.gap_scenario && (
                <p className="text-gray-400">سناریوی شکاف شبانه: زیان حدود {num(rec.exit_assessment.overnight.gap_scenario.loss_toman)} تومان ({rec.exit_assessment.overnight.gap_scenario.description})</p>
              )}
            </div>
          )}
          <div className="grid md:grid-cols-3 gap-3">
            <List title="شواهد موافق" items={rec.supporting} tone="text-emerald-300" />
            <List title="شواهد مخالف" items={rec.opposing} tone="text-rose-300" />
            <List title="اطلاعات ناموجود / محدودیت‌ها" items={rec.missing} tone="text-gray-400" />
          </div>
          <List title="اثر در سطح پرتفوی" items={rec.portfolio_implications} />
          <List title="تغییرات نسبت به تحلیل قبل" items={report.changes_since_previous} tone="text-sky-200" />
          <p className="text-[11px] text-gray-500">اطمینان: {rec.confidence?.level} — {rec.confidence?.basis} | {rec.targets_note} | بازبینی بعدی: {rec.next_review} | اعتبار تا {when(rec.valid_until)}</p>
        </div>
      )}

      {tab === "data" && (
        <div>
          <p className="text-xs text-gray-400 mb-2">هویت: {report.identity.name} | شناسه {report.identity.ins_id ?? "—"} | ISIN {report.identity.isin ?? "—"} | {report.identity.market ?? "—"} | وضعیت: {report.identity.trading_state ?? "نامشخص"} | مبنا: {report.identity.basis}</p>
          <table className="w-full text-xs">
            <thead><tr className="text-gray-500 text-right"><th className="py-1">داده</th><th>وضعیت</th><th>زمان داده</th><th>منبع</th><th>توضیح</th></tr></thead>
            <tbody>{Object.entries(report.coverage as Dict).map(([key, c]) => (
              <tr key={key} className="border-t border-surface-700/40">
                <td className="py-1 font-mono">{key}</td>
                <td className={COVERAGE_TONE[(c as Dict).status] ?? ""}>{COVERAGE_LABEL[(c as Dict).status] ?? (c as Dict).status}</td>
                <td>{(c as Dict).as_of ? when((c as Dict).as_of) : "—"}</td>
                <td className="text-gray-500" dir="ltr">{(c as Dict).source}</td>
                <td className="text-gray-400">{(c as Dict).detail}</td>
              </tr>))}</tbody>
          </table>
        </div>
      )}

      {tab === "market" && (m ? (
        <div className="text-xs text-gray-300 space-y-1">
          <p>آخرین {num(m.price_last)} | پایانی {num(m.price_close)} | دیروز {num(m.price_yesterday)} | تغییر {num(m.change_pct, 2)}٪ | دامنهٔ مجاز روز {num(m.low_limit)} – {num(m.high_limit)} (ریال، تعدیل‌نشده)</p>
          <p>شکاف خرید/فروش: {m.spread.state} {m.spread.pct != null ? `(${num(m.spread.pct, 2)}٪)` : ""} | صف: {m.queue.state}{m.queue.volume ? ` — ${num(m.queue.volume)} واحد، ${num(m.queue.orders)} سفارش` : ""} | عدم‌توازن دفتر: {num(m.book_imbalance, 2)}</p>
          <p>عمق قابل اجرا — خرید: {num(m.bid_depth.volume)} واحد | فروش: {num(m.ask_depth.volume)} واحد | حجم نسبی: {num(m.relative_volume, 2)}× | میانگین وزنی جلسه: {num(m.session_vwap)}</p>
          <p>نوسان روزانه: {num(m.daily_volatility_pct, 2)}٪ | بازده ۵ جلسه: {num(m.return_5d_pct, 2)}٪ | ۲۰ جلسه: {num(m.return_20d_pct, 2)}٪ | جلسات تاریخچه: {m.history_sessions}{m.history_discontinuities ? ` | ناپیوستگی: ${m.history_discontinuities}` : ""}</p>
          <List title="محدودیت‌ها" items={m.limitations} tone="text-gray-500" />
        </div>
      ) : <p className="text-xs text-gray-500">دادهٔ بازار معتبر در دسترس نیست؛ آخرین وضعیت در «پوشش داده» آمده است.</p>)}

      {tab === "options" && (
        <div className="text-xs text-gray-300 space-y-2">
          <p>
            {opt.state === "none" && "هیچ قرارداد اختیاری با شناسهٔ این ابزار به‌عنوان دارایی پایه ثبت نشده است."}
            {opt.state === "unavailable" && "دادهٔ اختیار معامله در دسترس نیست (این با «نبودِ اختیار» فرق دارد)."}
            {opt.state === "stale" && `قراردادهای مرتبط وجود دارند (${opt.summary?.contracts_listed}) اما داده کهنه است و تحلیل نمی‌شود.`}
            {opt.state === "available" && `${opt.summary.contracts_listed} قرارداد (${opt.summary.calls} خرید / ${opt.summary.puts} فروش)، ${opt.summary.contracts_active} فعال، ${opt.summary.contracts_with_reliable_iv} با نوسان ضمنی قابل اتکا | نزدیک‌ترین سررسید: ${num(opt.summary.nearest_expiry_days)} روز | نسبت حجم فروش/خرید: ${num(opt.summary.put_call_volume_ratio, 2)} (فقط توصیفی)`}
          </p>
          <p className="text-gray-500">{opt.scope} — فرض نرخ بدون ریسک: {num((opt.assumptions?.risk_free_rate ?? 0) * 100, 0)}٪ | {opt.assumptions?.model}</p>
          {opt.contracts?.length > 0 && (
            <div className="overflow-x-auto"><table className="w-full text-[11px] text-center">
              <thead><tr className="text-gray-500"><th>قرارداد</th><th>نوع</th><th>اعمال</th><th>روز</th><th>خرید</th><th>فروش</th><th>حجم</th><th>موقعیت باز</th><th>ارزش ذاتی</th><th>ارزش زمانی</th><th>سربه‌سر</th><th>IV</th><th>دلتا</th></tr></thead>
              <tbody>{opt.contracts.map((c: Dict) => (
                <tr key={c.symbol} className="border-t border-surface-700/40">
                  <td>{c.symbol}</td><td>{c.type === "call" ? "خرید" : "فروش"}</td><td>{num(c.strike)}</td><td>{num(c.days_remaining)}</td><td>{num(c.bid)}</td><td>{num(c.ask)}</td>
                  <td>{num(c.volume)}</td><td>{num(c.open_interest)}</td><td>{num(c.intrinsic)}</td><td>{num(c.time_value)}</td><td>{num(c.breakeven_cost_adjusted)}</td>
                  <td title={c.iv_reason ?? ""}>{c.iv != null ? `${num(c.iv * 100, 1)}٪` : "—"}</td><td>{c.greeks ? num(c.greeks.delta, 2) : "—"}</td>
                </tr>))}</tbody>
            </table></div>
          )}
        </div>
      )}

      {tab === "nav" && (report.nav ? (
        <div className="text-xs text-gray-300 space-y-1">
          <p>NAV رسمی ابطال: {num(report.nav.official_nav_redemption)} | صدور: {num(report.nav.official_nav_issue)} ریال — تاریخ {report.nav.official_date} {report.nav.official_time} — وضعیت: <span className={COVERAGE_TONE[report.nav.status] ?? ""}>{COVERAGE_LABEL[report.nav.status] ?? report.nav.status}</span></p>
          <p>حباب/تخفیف قیمت: {report.nav.premium_pct != null ? `${num(report.nav.premium_pct, 2)}٪` : `محاسبه نشد — ${report.nav.premium_note}`}</p>
          <p className="text-gray-500">NAV برآوردی: {report.nav.estimated_nav_note}</p>
          <List title="محدودیت‌های این نوع ابزار" items={report.identity.limitations} tone="text-gray-500" />
        </div>
      ) : (
        <div className="text-xs text-gray-400 space-y-1">
          <p>برای این ابزار NAV منتشرشده‌ای ذخیره نشده یا کاربرد ندارد.</p>
          <List title="محدودیت‌های این نوع ابزار" items={report.identity.limitations} tone="text-gray-500" />
        </div>
      ))}

      {tab === "events" && (report.disclosures?.length ? (
        <ul className="text-xs text-gray-300 space-y-1">
          {report.disclosures.map((x: Dict, i: number) => <li key={i}>{x.published_jalali} {x.time} — {x.title}</li>)}
          <li className="text-gray-600">عنوان‌ها متن خام منبع (کدال) هستند و تفسیر نشده‌اند.</li>
        </ul>
      ) : <p className="text-xs text-gray-500">افشایی برای این نماد ذخیره نشده است.</p>)}

      {tab === "history" && (
        <table className="w-full text-xs text-center">
          <thead><tr className="text-gray-500"><th>زمان</th><th>نتیجه</th><th>موضوع</th><th>رژیم</th><th>قواعد</th><th>تنظیمات</th><th>اعتبار تا</th></tr></thead>
          <tbody>{(d.history as Dict[]).map((h) => (
            <tr key={h.id} className="border-t border-surface-700/40"><td>{when(h.created_at)}</td><td>{h.state_label}</td><td>{h.subject === "confirmed_position" ? "موقعیت" : "جدید"}</td><td>{h.regime}</td><td>{h.rules_version}</td><td>v{h.settings_version}</td><td>{when(h.valid_until)}</td></tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}

function LedgerForm({ onDone, onError }: { onDone: () => Promise<void>; onError: (m: string) => void }) {
  const [type, setType] = useState("buy");
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("0");
  const [amount, setAmount] = useState("");
  const isTrade = type === "buy" || type === "sell";
  async function submit() {
    try {
      await apiPost("/alerts/engine/ledger", isTrade
        ? { entry_type: type, symbol, quantity: Number(quantity), price_rial: Number(price), fees_toman: Number(fees) || 0 }
        : { entry_type: type, amount_toman: Number(amount) });
      await onDone();
    } catch (err) { onError(describeApiError(err, "ثبت ناموفق بود.")); }
  }
  const input = "bg-surface-800 border border-surface-700 rounded-lg px-2 py-1 text-xs text-white w-32";
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <select value={type} onChange={(e) => setType(e.target.value)} className={input}>
        <option value="buy">خرید اجراشده</option><option value="sell">فروش اجراشده</option>
        <option value="deposit">واریز</option><option value="withdrawal">برداشت</option>
      </select>
      {isTrade ? (<>
        <input className={input} placeholder="نماد" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
        <input className={input} type="number" placeholder="تعداد اجراشده" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <input className={input} type="number" placeholder="قیمت اجرا (ریال)" value={price} onChange={(e) => setPrice(e.target.value)} />
        <input className={input} type="number" placeholder="کارمزد (تومان)" value={fees} onChange={(e) => setFees(e.target.value)} />
      </>) : <input className={input} type="number" placeholder="مبلغ (تومان)" value={amount} onChange={(e) => setAmount(e.target.value)} />}
      <button onClick={submit} className="px-3 py-1 rounded-lg bg-primary-600 text-white">ثبت</button>
      <span className="text-gray-500 basis-full">فقط معامله‌ای را ثبت کنید که واقعاً اجرا شده است (اجرای بخشی = همان تعداد اجراشده). توصیه‌ها هرگز به‌طور خودکار «اجراشده» فرض نمی‌شوند.</span>
    </div>
  );
}
