"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import { capturePortfolioSnapshot, getPortfolioPerformance, isServiceUnavailable } from "@/lib/goldApi";
import { ConfirmDialog } from "@/components/gold/ConfirmDialog";

interface Holding {
  // id فقط وقتی گروه یک ردیف دارد می‌آید؛ گروه چندردیفی `holding_ids` دارد.
  id?: number;
  holding_ids?: number[];
  symbol: string;
  display_name: string;
  quantity: number;
  avg_buy_price: number;
  // سمت سرور این چهار فیلد عمداً `float | None` هستند: نبودِ قیمت نباید P&L را
  // صفر یا منفی جعلی کند (اشارهٔ GS-17 در همان فایل). تایپ قبلی غیرnullable بود و
  // `.toFixed()` روی null صفحه را می‌انداخت.
  current_price: number | null;
  cost_basis: number;
  current_value: number | null;
  pnl_irt: number | null;
  pnl_pct: number | null;
  n_purchases: number;
}

interface Portfolio {
  total_cost: number;
  total_value: number;
  // null یعنی هیچ دارایی قیمت‌داری وجود ندارد؛ صفر یک P&L واقعی نیست (W4-04).
  total_pnl: number | null;
  total_pnl_pct: number | null;
  holdings: Holding[];
  snapshot_at: string | null;
  // C7: هزینهٔ فقط دارایی‌های قیمت‌دار؛ مخرج P&L کل همین است. اختیاری تا وقتی
  // بک‌اند آن را expose کند.
  priced_cost?: number | null;
  unpriced_holdings?: number;
}

interface PlanStatus {
  plan_id: number;
  name: string;
  status: {
    total_capital: number;
    executed: number;
    remaining: number;
    next_tranche_pct: number;
    next_tranche_amount: number;
    next_trigger: string;
    stop_loss_pct: number;
    take_profit_pct: number;
  };
}

interface Trade {
  id: number;
  symbol: string;
  action: "buy" | "sell";
  quantity: number;
  price: number;
  amount_irt: number;
  fee_irt: number;
  pnl_irt: number | null;
  note: string | null;
  traded_at: string | null;
}

/** هیچ عددی روی null/undefined تبدیل نمی‌شود — «—» یعنی داده نیست، نه صفر. */
const fmt = (n: number | null | undefined) =>
  n === null || n === undefined || !Number.isFinite(n) ? "—" : n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });

const signedFmt = (n: number | null | undefined) =>
  n === null || n === undefined || !Number.isFinite(n) ? "—" : `${n >= 0 ? "+" : ""}${fmt(n)}`;

const signedPct = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined || !Number.isFinite(n) ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(digits)}٪`;

/** idهای یک ردیف پورتفو: اولویت با holding_ids (گروه)، بعد id تک‌ردیفی. */
function holdingIds(holding: Holding): number[] {
  const ids = (holding.holding_ids ?? []).filter((id) => Number.isFinite(id));
  if (ids.length > 0) return ids;
  return typeof holding.id === "number" ? [holding.id] : [];
}

/** status کد HTTP از پیام خطای `@/lib/api` ("HTTP 409: ..."). */
function httpStatus(error: unknown): number | null {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const match = /^HTTP (\d{3})/.exec(message);
  return match ? Number(match[1]) : null;
}

async function getPortfolio(): Promise<Portfolio> {
  const r = await apiGet<{ success: boolean; data: Portfolio }>("/gold/portfolio");
  return r.data;
}

/**
 * C4: `current_score` دیگر از کلاینت نمی‌آید؛ بک‌اند آن را از snapshot سرور
 * می‌خواند. مسیر GET این پارامتر را optional با پیش‌فرض نگه داشته
 * (`api.py:1047`)، پس حذفش از همین حالا امن است.
 */
async function getPlans(): Promise<PlanStatus[]> {
  const r = await apiGet<{ success: boolean; data: PlanStatus[] }>("/gold/portfolio/dca");
  return r.data;
}

async function getTrades(): Promise<Trade[]> {
  const r = await apiGet<{ success: boolean; data: Trade[] }>("/gold/portfolio/trades?limit=20");
  return r.data;
}

export default function GoldPortfolioPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"overview" | "add" | "dca" | "trades">("overview");

  const { data: portfolio, isError: portfolioError, error: portfolioErr } = useQuery({
    queryKey: ["gold", "portfolio"],
    queryFn: getPortfolio,
    refetchInterval: 60_000,
  });

  const { data: plans } = useQuery({
    queryKey: ["gold", "plans"],
    queryFn: getPlans,
    refetchInterval: 60_000,
  });

  const { data: trades } = useQuery({
    queryKey: ["gold", "trades"],
    queryFn: getTrades,
    refetchInterval: 60_000,
  });

  const invalidatePlans = () => {
    qc.invalidateQueries({ queryKey: ["gold", "plans"] });
    qc.invalidateQueries({ queryKey: ["gold", "portfolio"] });
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* F3: ابزار تحلیلی است، نه توصیهٔ مالی — روی همهٔ تب‌ها دیده می‌شود. */}
      <div
        className="rounded-lg px-3 py-2 text-[11px] leading-5"
        style={{ background: "var(--gd-bg-2)", color: "var(--gd-text-2)", border: "1px solid var(--gd-border)" }}
      >
        این ابزار صرفاً تحلیلی است و توصیهٔ مالی نیست. مسئول خرید و فروش با خودِ کاربر است.
      </div>

      {portfolioError && (
        <div className="rounded-lg border border-rose-700/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">
          {isServiceUnavailable(portfolioErr)
            ? "سرویس دادهٔ طلا موقتاً در دسترس نیست (۵۰۳)؛ چند لحظه دیگر دوباره تلاش کنید."
            : "دریافت پورتفو ناموفق بود."}
        </div>
      )}

      <div className="flex gap-1 border-b" style={{ borderColor: "var(--gd-border)" }}>
        {(["overview", "add", "dca", "trades"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition ${
              tab === t
                ? "border-amber-500 text-amber-300 font-semibold"
                : "border-transparent hover:text-zinc-200"
            }`}
            style={{ color: tab === t ? undefined : "var(--gd-text-2)" }}
          >
            {t === "overview" ? "نمای کلی" : t === "add" ? "ثبت خرید" : t === "dca" ? "پلن‌های DCA" : "تاریخچه"}
          </button>
        ))}
      </div>

      {tab === "overview" && portfolio && (
        <div className="space-y-4">
          <OverviewTab
            portfolio={portfolio}
            onChanged={() => {
              qc.invalidateQueries({ queryKey: ["gold", "portfolio"] });
              qc.invalidateQueries({ queryKey: ["gold", "plans"] });
              qc.invalidateQueries({ queryKey: ["gold", "trades"] });
            }}
          />
          <PerformancePanel />
        </div>
      )}

      {tab === "add" && (
        <AddHoldingTab onAdded={() => qc.invalidateQueries({ queryKey: ["gold", "portfolio"] })} />
      )}

      {tab === "dca" && <DCATab plans={plans ?? []} onChange={invalidatePlans} />}

      {tab === "trades" && trades && <TradesTab trades={trades} />}
    </div>
  );
}

function OverviewTab({ portfolio, onChanged }: { portfolio: Portfolio; onChanged: () => void }) {
  const [pendingDelete, setPendingDelete] = useState<Holding | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [pendingSell, setPendingSell] = useState<Holding | null>(null);
  const [sellError, setSellError] = useState<string | null>(null);
  const [selling, setSelling] = useState(false);
  const [sellQuantity, setSellQuantity] = useState(1);
  const [sellPrice, setSellPrice] = useState(0);

  const pendingIds = pendingDelete ? holdingIds(pendingDelete) : [];

  const confirmDelete = async () => {
    if (pendingIds.length === 0) return;
    setDeleting(true);
    setDeleteError(null);
    let alreadyDeleted = false;
    try {
      // هر id پشت‌سرهم و بدون ?force=true؛ 409 یعنی قبلاً حذف شده و بقیه ادامه می‌یابند.
      for (const id of pendingIds) {
        try {
          await apiDelete(`/gold/portfolio/holdings/${id}`);
        } catch (error) {
          const status = httpStatus(error);
          if (status === 409) {
            alreadyDeleted = true;
            continue;
          }
          setDeleteError(
            status === 404
              ? "دارایی پیدا نشد؛ لیست به‌روزرسانی شد."
              : "ارتباط با سرور برقرار نشد؛ لیست به‌روزرسانی شد.",
          );
          break;
        }
      }
      if (alreadyDeleted) {
        setDeleteError("این دارایی قبلاً حذف شده بود؛ لیست به‌روزرسانی شد.");
      }
    } finally {
      setDeleting(false);
      setPendingDelete(null);
      onChanged();
    }
  };

  const openSell = (holding: Holding) => {
    setPendingSell(holding);
    setSellQuantity(1);
    setSellPrice(holding.current_price ?? 0);
    setSellError(null);
  };

  const submitSell = async () => {
    const holding = pendingSell;
    if (!holding || selling) return;
    // فقط idهایی که همین حالا در پاسخ /portfolio هستند؛ id کهنه/حدسی ارسال نمی‌شود.
    const ids = holdingIds(holding);
    const freshIds = portfolio.holdings
      .filter((row) => row.symbol === holding.symbol)
      .flatMap((row) => holdingIds(row));
    if (ids.length === 0 || !ids.every((id) => freshIds.includes(id))) {
      setSellError("لیست پورتفو تغییر کرده است؛ دوباره تلاش کنید.");
      onChanged();
      return;
    }
    if (sellQuantity <= 0 || sellPrice <= 0) {
      setSellError("تعداد و قیمت باید بزرگ‌تر از صفر باشند.");
      return;
    }
    if (sellQuantity > holding.quantity) {
      setSellError(`حداکثر مقدار قابل فروش ${fmt(holding.quantity)} است.`);
      return;
    }
    setSelling(true);
    setSellError(null);
    try {
      await apiPost("/gold/portfolio/trades", {
        symbol: holding.symbol,
        action: "sell",
        quantity: sellQuantity,
        price: sellPrice,
        amount_irt: sellQuantity * sellPrice,
        // گروه چندردیفی: همهٔ lotها با هم؛ سرور FIFO توزیع می‌کند (W4-08).
        holding_ids: ids,
      });
      setPendingSell(null);
      onChanged();
    } catch (error) {
      const status = httpStatus(error);
      setSellError(
        status === 409
          ? "فروش ثبت نشد: موجودی کافی نیست یا دارایی حذف شده است."
          : status === 404
            ? "دارایی پیدا نشد؛ پورتفو به‌روزرسانی شد."
            : "ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید.",
      );
      if (status === 404 || status === 409) onChanged();
    } finally {
      setSelling(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard label="ارزش فعلی" value={fmt(portfolio.total_value)} unit="ریال" />
        <StatCard label="هزینه" value={fmt(portfolio.total_cost)} unit="ریال" />
        <StatCard
          label="P&L"
          value={signedFmt(portfolio.total_pnl)}
          unit="ریال"
          sub={
            // C7: مخرج P&L کل فقط دارایی‌های قیمت‌دار است؛ null/0 یعنی «نامعلوم».
            !portfolio.priced_cost
              ? `${signedPct(portfolio.total_pnl_pct)} · سرمایهٔ قیمت‌دار: —`
              : `${signedPct(portfolio.total_pnl_pct)} · روی هزینهٔ ${fmt(portfolio.priced_cost)} قیمت‌دار`
          }
          tone={
            portfolio.total_pnl === null || portfolio.total_pnl === undefined
              ? undefined
              : portfolio.total_pnl >= 0
                ? "good"
                : "bad"
          }
        />
      </div>

      {!!portfolio.unpriced_holdings && (
        <div
          className="rounded-lg px-3 py-2 text-[11px] leading-5"
          style={{ background: "var(--gd-bg-2)", color: "var(--gd-warn)", border: "1px solid var(--gd-border)" }}
        >
          {portfolio.unpriced_holdings} دارایی قیمت فعلی ندارد؛ P&L آن‌ها «—» است و در
          مجموع سود/زیان حساب نشده‌اند (صفر جعلی ساخته نمی‌شود).
        </div>
      )}

      {deleteError && (
        <div
          role="alert"
          className="rounded-lg border px-4 py-3 text-sm"
          style={{ borderColor: "var(--gd-danger)", background: "var(--gd-bg-2)", color: "var(--gd-danger)" }}
        >
          {deleteError}
        </div>
      )}

      <div className="rounded-xl overflow-hidden" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
        <div className="px-4 py-3 text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
          دارایی‌ها ({portfolio.holdings.length})
        </div>
        {portfolio.holdings.length === 0 ? (
          <div className="p-8 text-center text-sm" style={{ color: "var(--gd-text-2)" }}>
            هنوز خریدی ثبت نشده — از تب «ثبت خرید» شروع کنید
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>
                <th className="text-right p-3">نماد</th>
                <th className="text-left p-3">تعداد</th>
                <th className="text-left p-3">میانگین خرید</th>
                <th className="text-left p-3">قیمت فعلی</th>
                <th className="text-left p-3">ارزش</th>
                <th className="text-left p-3">P&L</th>
                <th className="text-left p-3">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.holdings.map((h) => (
                <tr key={h.symbol} style={{ borderTop: "1px solid var(--gd-border)" }}>
                  <td className="p-3" style={{ color: "var(--gd-text)" }}>{h.display_name}</td>
                  <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text-2)" }}>{h.quantity.toFixed(2)}</td>
                  <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text-2)" }}>{fmt(h.avg_buy_price)}</td>
                  <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text)" }}>{fmt(h.current_price)}</td>
                  <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text)" }}>{fmt(h.current_value)}</td>
                  <td
                    className="p-3 text-left font-mono font-bold"
                    style={{
                      // نبودِ داده خنثی است، نه سبز/قرمز (F3).
                      color: h.pnl_irt === null || h.pnl_irt === undefined ? "var(--gd-text-3)" : h.pnl_irt >= 0 ? "var(--gd-success)" : "var(--gd-danger)",
                    }}
                  >
                    {signedFmt(h.pnl_irt)} ({signedPct(h.pnl_pct, 1)})
                  </td>
                  <td className="p-3 text-left">
                    {(() => {
                      const ids = holdingIds(h);
                      return (
                        <div className="flex items-center justify-end gap-3">
                          {ids.length > 0 && (
                            <button
                              onClick={() => openSell(h)}
                              className="text-xs"
                              style={{ color: "var(--gd-text-2)" }}
                              aria-label={`ثبت فروش برای ${h.display_name}`}
                            >
                              فروش
                            </button>
                          )}
                          {ids.length > 0 ? (
                            <button
                              onClick={() => setPendingDelete(h)}
                              className="text-xs"
                              style={{ color: "var(--gd-danger)" }}
                              aria-label={`حذف دارایی ${h.display_name}`}
                            >
                              حذف
                            </button>
                          ) : (
                            <span className="text-[10px]" style={{ color: "var(--gd-text-3)" }} title="شناسهٔ دارایی در پاسخ سرور نیست">
                              —
                            </span>
                          )}
                        </div>
                      );
                    })()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`حذف دارایی «${pendingDelete?.display_name ?? ""}»؟`}
        description={
          <>
            <div className="font-semibold" style={{ color: "var(--gd-danger)" }}>
              {pendingIds.length > 1
                ? `این نماد ${pendingIds.length.toLocaleString("fa-IR")} ردیف دارد؛ همه حذف نرم می‌شوند و معاملات حفظ می‌شوند.`
                : "معامله‌های این دارایی هم تحت‌تأثیرند."}
            </div>
            <div className="mt-2">
              حذف به‌صورت نرم (soft-delete) انجام می‌شود: ردیف دارایی از نمای پورتفو
              خارج می‌شود ولی خودش و معامله‌های ثبت‌شدهٔ آن در دیتابیس می‌مانند، پس
              گزارش مالیاتی سوراخ نمی‌شود. برای برگرداندن باید از سمت سرور
              operation انجام شود — این کار قابل بازگشت از UI نیست.
            </div>
          </>
        }
        confirmLabel={deleting ? "در حال حذف..." : "حذف نرم"}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      <ConfirmDialog
        open={pendingSell !== null}
        title={`ثبت فروش «${pendingSell?.display_name ?? ""}»`}
        description={
          <>
            <div className="space-y-2">
              <label className="block text-xs" style={{ color: "var(--gd-text-2)" }}>
                تعداد فروش
                <input
                  aria-label="تعداد فروش"
                  type="number"
                  step="0.01"
                  value={sellQuantity}
                  onChange={(event) => setSellQuantity(parseFloat(event.target.value) || 0)}
                  className="w-full mt-1 px-3 py-2 rounded text-sm"
                  style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}
                />
              </label>
              <label className="block text-xs" style={{ color: "var(--gd-text-2)" }}>
                قیمت فروش (ریال)
                <input
                  aria-label="قیمت فروش (ریال)"
                  type="number"
                  value={sellPrice}
                  onChange={(event) => setSellPrice(parseFloat(event.target.value) || 0)}
                  className="w-full mt-1 px-3 py-2 rounded text-sm"
                  style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}
                />
              </label>
              <div className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>
                این معامله فقط به ردیف {pendingSell?.id ?? "—"} از پاسخ تازهٔ پورتفو متصل می‌شود.
              </div>
            </div>
            {sellError && (
              <div role="alert" className="mt-3 font-semibold" style={{ color: "var(--gd-danger)" }}>
                {sellError}
              </div>
            )}
          </>
        }
        confirmLabel={selling ? "در حال ثبت..." : "ثبت فروش"}
        onConfirm={submitSell}
        onCancel={() => {
          setPendingSell(null);
          setSellError(null);
        }}
      />
    </div>
  );
}

type Performance = Awaited<ReturnType<typeof getPortfolioPerformance>>;

function pct(value: number | null, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}٪`;
}

const BENCH_LABELS: Record<string, string> = {
  gold: "طلا",
  usd: "دلار",
  tedpix: "شاخص کل",
};

/** کارایی/ریسک پرتفوی: TWR، نوسان، افت، تمرکز و مقایسه با بنچمارک‌ها. */
function PerformancePanel() {
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);

  const { data: perf, isLoading } = useQuery<Performance>({
    queryKey: ["gold", "portfolio", "performance"],
    queryFn: () => getPortfolioPerformance(90),
    refetchInterval: 120_000,
  });

  const onCapture = async () => {
    setSaving(true);
    try {
      await capturePortfolioSnapshot();
      qc.invalidateQueries({ queryKey: ["gold", "portfolio"] });
      qc.invalidateQueries({ queryKey: ["gold", "portfolio", "performance"] });
    } finally {
      setSaving(false);
    }
  };

  if (isLoading || !perf) {
    return (
      <div className="rounded-xl p-6 text-center text-sm" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)", color: "var(--gd-text-2)" }}>
        در حال محاسبهٔ کارایی...
      </div>
    );
  }

  const drift = Object.entries(perf.drift_by_class ?? {});

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
      <div className="px-4 py-3 flex items-center justify-between gap-3">
        <div className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
          کارایی و ریسک ({perf.points.toLocaleString("fa-IR")} روز داده)
        </div>
        <button
          onClick={onCapture}
          disabled={saving}
          className="text-xs rounded-lg px-3 py-1.5 bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 disabled:opacity-50"
        >
          {saving ? "در حال ثبت..." : "ثبت ارزش امروز"}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-px" style={{ background: "var(--gd-border)" }}>
        {(
          [
            ["TWR (وزنی‌زمان)", perf.twr_pct, true],
            ["بازده کل", perf.simple_return_pct, true],
            ["بیشترین افت", perf.max_drawdown_pct, false],
            ["نوسان سالانه", perf.annualized_volatility_pct, false],
            ["شارپ", perf.sharpe_ratio, true],
            ["سورتینو", perf.sortino_ratio, true],
            ["VaR ۹۵٪", perf.var_95_pct, false],
            ["تمرکز", perf.concentration_pct, false],
          ] as const
        ).map(([label, value, isGain]) => {
          const isRatio = label === "شارپ" || label === "سورتینو";
          const displayed = value === null ? "—" : isRatio ? value.toFixed(2) : pct(value);
          const tone =
            value === null || !isGain ? "" : value >= 0 ? "text-emerald-400" : "text-rose-400";
          return (
            <div key={label} className="p-3" style={{ background: "var(--gd-bg-2)" }}>
              <div className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>{label}</div>
              <div
                className={`font-mono font-bold text-sm ${tone}`}
                style={value === null || !isGain ? { color: "var(--gd-text)" } : undefined}
              >
                {displayed}
              </div>
            </div>
          );
        })}
      </div>

      <div className="p-4 space-y-3" style={{ borderTop: "1px solid var(--gd-border)" }}>
        <div className="text-xs font-semibold" style={{ color: "var(--gd-text-2)" }}>
          مقایسه با بنچمارک ({perf.window_days.toLocaleString("fa-IR")} روز)
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>
              <th className="text-right pb-2">بنچمارک</th>
              <th className="text-left pb-2">بازده</th>
              <th className="text-left pb-2">نسبت به پرتفوی</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(perf.benchmarks ?? {}).map(([key, b]) => (
              <tr key={key} style={{ borderTop: "1px solid var(--gd-border)" }}>
                <td className="py-2" style={{ color: "var(--gd-text)" }}>
                  {BENCH_LABELS[key] ?? b.label}
                </td>
                <td className="py-2 text-left font-mono" style={{ color: "var(--gd-text-2)" }}>{pct(b.return_pct)}</td>
                <td
                  className={`py-2 text-left font-mono font-bold ${
                    b.relative_pct === null ? "" : b.relative_pct >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                  style={b.relative_pct === null ? { color: "var(--gd-text-3)" } : undefined}
                >
                  {pct(b.relative_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {drift.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {drift.map(([cls, value]) => (
              <span
                key={cls}
                className="text-[11px] rounded-lg px-2 py-1"
                style={{ background: "var(--gd-bg-3, #18181b)", color: "var(--gd-text-2)" }}
              >
                {cls === "coin" ? "سکه" : cls === "melted" ? "طلا" : "صندوق"}: انحراف {pct(value, 1)}
              </span>
            ))}
          </div>
        )}

        {Object.keys(perf.unavailable ?? {}).length > 0 && (
          <div className="text-[10px] leading-5" style={{ color: "var(--gd-text-3)" }}>
            {Object.entries(perf.unavailable).map(([k, reason]) => (
              <div key={k}>• {reason}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AddHoldingTab({ onAdded }: { onAdded: () => void }) {
  const [symbol, setSymbol] = useState("IR_COIN_EMAMI");
  const [name, setName] = useState("سکه امامی");
  // A coin purchase must not be stored as an ETF (the old default was "etf").
  const [vehicle, setVehicle] = useState("coin");
  const [quantity, setQuantity] = useState(1);
  const [buyPrice, setBuyPrice] = useState(0);
  const [amount, setAmount] = useState(0);
  const [feePct, setFeePct] = useState(0);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    if (quantity <= 0 || buyPrice <= 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiPost("/gold/portfolio/holdings", {
        symbol,
        display_name: name,
        vehicle,
        quantity,
        buy_price: buyPrice,
        buy_amount_irt: amount || quantity * buyPrice,
        buy_fee_pct: feePct,
        note: note || null,
      });
      onAdded();
      setQuantity(1);
      setBuyPrice(0);
      setAmount(0);
      setFeePct(0);
      setNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "ثبت خرید ناموفق بود.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-md rounded-xl p-4 space-y-3" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
      <h3 className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>ثبت خرید جدید</h3>
      <p className="text-[11px]" style={{ color: "var(--gd-text-2)" }}>همهٔ مبالغ در این صفحه به ریال وارد و نمایش داده می‌شوند.</p>
      <input
        value={symbol}
        onChange={(e) => {
          const next = e.target.value;
          setSymbol(next);
          setVehicle(next.startsWith("IR_COIN") ? "coin" : next.startsWith("IR_GOLD") ? "melted" : "etf");
        }}
        placeholder="IR_COIN_EMAMI"
        className="w-full px-3 py-2 rounded text-sm"
        style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}
      />
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="نام" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <select value={vehicle} onChange={(e) => setVehicle(e.target.value)} className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}>
        <option value="etf">صندوق ETF</option>
        <option value="cert">گواهی شمش</option>
        <option value="melted">طلای آب‌شده</option>
        <option value="coin">سکه فیزیکی</option>
      </select>
      <input type="number" step="0.01" value={quantity} onChange={(e) => setQuantity(parseFloat(e.target.value) || 0)} placeholder="تعداد" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input type="number" value={buyPrice} onChange={(e) => setBuyPrice(parseFloat(e.target.value) || 0)} placeholder="قیمت خرید (ریال)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input type="number" value={amount} onChange={(e) => setAmount(parseFloat(e.target.value) || 0)} placeholder="مبلغ کل (ریال، اختیاری)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input type="number" step="0.01" value={feePct} onChange={(e) => setFeePct(parseFloat(e.target.value) || 0)} placeholder="کارمزد (٪، اختیاری)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="یادداشت (اختیاری)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      {error && <div className="rounded px-3 py-2 text-xs" style={{ color: "var(--gd-danger)", background: "var(--gd-bg-3)" }}>{error}</div>}
      <button onClick={onSubmit} disabled={submitting} className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold">
        {submitting ? "در حال ثبت..." : "ثبت خرید"}
      </button>
    </div>
  );
}

function DCATab({ plans, onChange }: { plans: PlanStatus[]; onChange: () => void }) {
  const [name, setName] = useState("");
  const [capital, setCapital] = useState(100_000_000);
  const [risk, setRisk] = useState<"balanced" | "conservative" | "aggressive">("balanced");
  const [submitting, setSubmitting] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PlanStatus | null>(null);
  const [deleting, setDeleting] = useState(false);

  const onCreate = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      // دو اصلاح هم‌زمان:
      //   ۱) قبلاً همهٔ فیلدها در query string می‌رفتند در حالی که این route بدنهٔ
      //      JSON می‌خواهد (`p: DCAPlanCreate` در api.py:991-999) — یعنی «ساخت پلن»
      //      با 422 می‌خوابست.
      //   ۲) C4: امتیاز دیگر از کلاینت نمی‌آید؛ بک‌اند آن را از snapshot سرور برمی‌دارد.
      await apiPost("/gold/portfolio/dca", {
        name: name.trim(),
        total_capital_irt: capital,
        risk_profile: risk,
        vehicle: "etf",
      });
      onChange();
      setName("");
    } finally {
      setSubmitting(false);
    }
  };

  const onExecute = async (planId: number, executed: number) => {
    await apiPost(`/gold/portfolio/dca/${planId}/execute?tranche=${executed + 1}`, {});
    onChange();
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await apiDelete(`/gold/portfolio/dca/${pendingDelete.plan_id}`);
      setPendingDelete(null);
      onChange();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl p-4 space-y-3" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
        <h3 className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>ساخت پلن DCA</h3>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="نام پلن" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
        <input type="number" value={capital} onChange={(e) => setCapital(parseInt(e.target.value) || 0)} placeholder="سرمایه (ریال)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
        <select value={risk} onChange={(e) => setRisk(e.target.value as "balanced" | "conservative" | "aggressive")} className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}>
          <option value="conservative">محافظه‌کار (20/40/40)</option>
          <option value="balanced">متعادل (30/40/30)</option>
          <option value="aggressive">تهاجمی (50/30/20)</option>
        </select>
        <div className="text-[11px] leading-5" style={{ color: "var(--gd-text-3)" }}>
          امتیاز بازار از اسنپ‌شات سمت سرور خوانده می‌شود؛ دیگر از این فرم وارد نمی‌شود (C4).
        </div>
        <button onClick={onCreate} disabled={submitting || !name.trim()} className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold">
          ساخت پلن
        </button>
      </div>

      {plans.map((p) => {
        const s = p.status;
        const isComplete = s.remaining === 0;
        return (
          <div key={p.plan_id} className="rounded-xl p-4" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>{p.name}</div>
                <div className="text-xs" style={{ color: "var(--gd-text-2)" }}>
                  سرمایه: {fmt(s.total_capital)} | اجرا: {s.executed}/3 | باقی: {s.remaining}
                </div>
              </div>
              <button
                onClick={() => setPendingDelete(p)}
                className="text-xs"
                style={{ color: "var(--gd-danger)" }}
                aria-label={`حذف پلن ${p.name}`}
              >
                حذف
              </button>
            </div>

            {isComplete ? (
              <div className="text-emerald-400 text-sm">✓ پلن کامل اجرا شد</div>
            ) : (
              <div className="space-y-2">
                <div className="rounded p-2" style={{ background: "var(--gd-bg-3)" }}>
                  <div className="text-xs" style={{ color: "var(--gd-text-2)" }}>پله بعدی: {(s.next_tranche_pct * 100).toFixed(0)}٪ = {fmt(s.next_tranche_amount)} ریال</div>
                  <div className="text-[10px] mt-1" style={{ color: "var(--gd-text-3)" }}>📌 {s.next_trigger}</div>
                </div>
                <div className="text-[10px] flex justify-between" style={{ color: "var(--gd-text-3)" }}>
                  <span>Stop: -%{s.stop_loss_pct}</span>
                  <span>TP: +%{s.take_profit_pct}</span>
                </div>
                <button onClick={() => onExecute(p.plan_id, s.executed)} className="w-full text-xs bg-amber-600 hover:bg-amber-500 text-white rounded py-1.5">
                  ✓ علامت‌گذاری پله {s.executed + 1} اجرا شد
                </button>
              </div>
            )}
          </div>
        );
      })}

      {plans.length === 0 && (
        <div className="text-sm text-center py-6" style={{ color: "var(--gd-text-2)" }}>
          پلنی نیست — اولین پلن را بسازید
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`حذف پلن «${pendingDelete?.name ?? ""}»؟`}
        description={
          <>
            پلن DCA و وضعیت اجرای پله‌هایش پاک می‌شود.
            <div className="mt-2">
              معامله‌هایی که با همین پلن ثبت شده‌اند حذف نمی‌شوند، ولی دیگر به پلنی
              متصل نخواهند بود.
            </div>
          </>
        }
        confirmLabel={deleting ? "در حال حذف..." : "حذف پلن"}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function TradesTab({ trades }: { trades: Trade[] }) {
  if (trades.length === 0) {
    return <div className="text-sm text-center py-8" style={{ color: "var(--gd-text-2)" }}>معامله‌ای ثبت نشده</div>;
  }
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>
            <th className="text-right p-3">زمان</th>
            <th className="text-right p-3">نماد</th>
            <th className="text-right p-3">نوع</th>
            <th className="text-left p-3">تعداد</th>
            <th className="text-left p-3">قیمت</th>
            <th className="text-left p-3">مبلغ</th>
            <th className="text-left p-3">P&L</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} style={{ borderTop: "1px solid var(--gd-border)" }}>
              <td className="p-3 text-xs" style={{ color: "var(--gd-text-2)" }}>{t.traded_at ? new Date(t.traded_at).toLocaleString("fa-IR") : "—"}</td>
              <td className="p-3" style={{ color: "var(--gd-text)" }}>{t.symbol}</td>
              <td className="p-3">
                <span className={`text-xs px-2 py-0.5 rounded ${t.action === "buy" ? "bg-emerald-700/30 text-emerald-300" : "bg-rose-700/30 text-rose-300"}`}>
                  {t.action === "buy" ? "خرید" : "فروش"}
                </span>
              </td>
              <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text-2)" }}>{t.quantity}</td>
              <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text-2)" }}>{fmt(t.price)}</td>
              <td className="p-3 text-left font-mono" style={{ color: "var(--gd-text)" }}>{fmt(t.amount_irt)}</td>
              <td
                className="p-3 text-left font-mono"
                style={{
                  // صفرِ واقعی «بدون داده» نیست (قبلاً truthiness این را گیج می‌زد).
                  color:
                    t.pnl_irt === null || t.pnl_irt === undefined
                      ? "var(--gd-text-3)"
                      : t.pnl_irt >= 0
                        ? "var(--gd-success)"
                        : "var(--gd-danger)",
                }}
              >
                {signedFmt(t.pnl_irt)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatCard({ label, value, unit, sub, tone }: { label: string; value: string; unit?: string; sub?: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-emerald-400" : tone === "bad" ? "text-rose-400" : "";
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--gd-text-2)" }}>{label}</div>
      <div className={`text-2xl font-bold font-mono ${color}`} style={{ color: tone ? undefined : "var(--gd-text)" }}>
        {value}
        {unit && <span className="text-xs mr-1" style={{ color: "var(--gd-text-3)" }}>{unit}</span>}
      </div>
      {sub && <div className={`text-xs mt-1 ${color}`}>{sub}</div>}
    </div>
  );
}
