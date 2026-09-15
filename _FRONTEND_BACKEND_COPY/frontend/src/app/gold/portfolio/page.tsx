"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

interface Holding {
  symbol: string;
  display_name: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  cost_basis: number;
  current_value: number;
  pnl_irt: number;
  pnl_pct: number;
  n_purchases: number;
}

interface Portfolio {
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings: Holding[];
  snapshot_at: string | null;
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
    current_score: number;
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
  pnl_irt: number;
  note: string | null;
  traded_at: string | null;
}

const fmt = (n: number) => n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });

async function getPortfolio(): Promise<Portfolio> {
  const r = await apiGet<{ success: boolean; data: Portfolio }>("/api/gold/portfolio");
  return r.data;
}

async function getPlans(currentScore: number): Promise<PlanStatus[]> {
  const r = await apiGet<{ success: boolean; data: PlanStatus[] }>(`/api/gold/portfolio/dca?current_score=${currentScore}`);
  return r.data;
}

async function getTrades(): Promise<Trade[]> {
  const r = await apiGet<{ success: boolean; data: Trade[] }>("/api/gold/portfolio/trades?limit=20");
  return r.data;
}

export default function GoldPortfolioPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"overview" | "add" | "dca" | "trades">("overview");
  const [currentScore, setCurrentScore] = useState(65);

  const { data: portfolio } = useQuery({
    queryKey: ["gold", "portfolio"],
    queryFn: getPortfolio,
    refetchInterval: 60_000,
  });

  const { data: plans } = useQuery({
    queryKey: ["gold", "plans", currentScore],
    queryFn: () => getPlans(currentScore),
    refetchInterval: 60_000,
  });

  const { data: trades } = useQuery({
    queryKey: ["gold", "trades"],
    queryFn: getTrades,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6" dir="rtl">
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
        <OverviewTab portfolio={portfolio} />
      )}

      {tab === "add" && (
        <AddHoldingTab onAdded={() => qc.invalidateQueries({ queryKey: ["gold", "portfolio"] })} />
      )}

      {tab === "dca" && (
        <DCATab
          plans={plans ?? []}
          currentScore={currentScore}
          onScoreChange={setCurrentScore}
          onChange={() => {
            qc.invalidateQueries({ queryKey: ["gold", "plans", currentScore] });
            qc.invalidateQueries({ queryKey: ["gold", "portfolio"] });
          }}
        />
      )}

      {tab === "trades" && trades && <TradesTab trades={trades} />}
    </div>
  );
}

function OverviewTab({ portfolio }: { portfolio: Portfolio }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard label="ارزش فعلی" value={fmt(portfolio.total_value)} unit="تومان" />
        <StatCard label="هزینه" value={fmt(portfolio.total_cost)} unit="تومان" />
        <StatCard
          label="P&L"
          value={(portfolio.total_pnl >= 0 ? "+" : "") + fmt(portfolio.total_pnl)}
          unit="تومان"
          sub={`${portfolio.total_pnl_pct >= 0 ? "+" : ""}${portfolio.total_pnl_pct.toFixed(2)}٪`}
          tone={portfolio.total_pnl >= 0 ? "good" : "bad"}
        />
      </div>

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
                  <td className={`p-3 text-left font-mono font-bold ${h.pnl_irt >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {h.pnl_irt >= 0 ? "+" : ""}
                    {fmt(h.pnl_irt)} ({h.pnl_pct >= 0 ? "+" : ""}
                    {h.pnl_pct.toFixed(1)}٪)
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function AddHoldingTab({ onAdded }: { onAdded: () => void }) {
  const [symbol, setSymbol] = useState("IR_COIN_EMAMI");
  const [name, setName] = useState("سکه امامی");
  const [vehicle, setVehicle] = useState("etf");
  const [quantity, setQuantity] = useState(1);
  const [buyPrice, setBuyPrice] = useState(0);
  const [amount, setAmount] = useState(0);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async () => {
    if (quantity <= 0 || buyPrice <= 0) return;
    setSubmitting(true);
    try {
      await apiPost("/api/gold/portfolio/holdings", {
        symbol,
        display_name: name,
        vehicle,
        quantity,
        buy_price: buyPrice,
        buy_amount_irt: amount || quantity * buyPrice,
        buy_fee_pct: 0,
        note: note || null,
      });
      onAdded();
      setQuantity(1);
      setBuyPrice(0);
      setAmount(0);
      setNote("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-md rounded-xl p-4 space-y-3" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
      <h3 className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>ثبت خرید جدید</h3>
      <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="IR_COIN_EMAMI" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="نام" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <select value={vehicle} onChange={(e) => setVehicle(e.target.value)} className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}>
        <option value="etf">صندوق ETF</option>
        <option value="cert">گواهی شمش</option>
        <option value="melted">طلای آب‌شده</option>
        <option value="coin">سکه فیزیکی</option>
      </select>
      <input type="number" step="0.01" value={quantity} onChange={(e) => setQuantity(parseFloat(e.target.value) || 0)} placeholder="تعداد" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input type="number" value={buyPrice} onChange={(e) => setBuyPrice(parseFloat(e.target.value) || 0)} placeholder="قیمت خرید (تومان)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input type="number" value={amount} onChange={(e) => setAmount(parseFloat(e.target.value) || 0)} placeholder="مبلغ کل (اختیاری)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="یادداشت (اختیاری)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
      <button onClick={onSubmit} disabled={submitting} className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold">
        {submitting ? "در حال ثبت..." : "ثبت خرید"}
      </button>
    </div>
  );
}

function DCATab({ plans, currentScore, onScoreChange, onChange }: { plans: PlanStatus[]; currentScore: number; onScoreChange: (s: number) => void; onChange: () => void }) {
  const [name, setName] = useState("");
  const [capital, setCapital] = useState(100_000_000);
  const [risk, setRisk] = useState<"balanced" | "conservative" | "aggressive">("balanced");
  const [submitting, setSubmitting] = useState(false);

  const onCreate = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await apiPost(`/api/gold/portfolio/dca?total_capital_irt=${capital}&risk_profile=${risk}&current_score=${currentScore}&vehicle=etf&name=${encodeURIComponent(name)}`, {});
      onChange();
      setName("");
    } finally {
      setSubmitting(false);
    }
  };

  const onExecute = async (planId: number, executed: number) => {
    await apiPost(`/api/gold/portfolio/dca/${planId}/execute?tranche=${executed + 1}`, {});
    onChange();
  };

  const onDelete = async (planId: number) => {
    if (!confirm("حذف شود؟")) return;
    await apiDelete(`/api/gold/portfolio/dca/${planId}`);
    onChange();
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl p-4 space-y-3" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
        <h3 className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>ساخت پلن DCA</h3>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="نام پلن" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
        <input type="number" value={capital} onChange={(e) => setCapital(parseInt(e.target.value) || 0)} placeholder="سرمایه (تومان)" className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
        <select value={risk} onChange={(e) => setRisk(e.target.value as "balanced" | "conservative" | "aggressive")} className="w-full px-3 py-2 rounded text-sm" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}>
          <option value="conservative">محافظه‌کار (20/40/40)</option>
          <option value="balanced">متعادل (30/40/30)</option>
          <option value="aggressive">تهاجمی (50/30/20)</option>
        </select>
        <div className="flex items-center gap-2 text-xs">
          <span style={{ color: "var(--gd-text-2)" }}>امتیاز فعلی:</span>
          <input type="number" min={0} max={100} value={currentScore} onChange={(e) => onScoreChange(parseInt(e.target.value) || 0)} className="w-20 px-2 py-1 rounded" style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }} />
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
              <button onClick={() => onDelete(p.plan_id)} className="text-xs text-rose-400">حذف</button>
            </div>

            {isComplete ? (
              <div className="text-emerald-400 text-sm">✓ پلن کامل اجرا شد</div>
            ) : (
              <div className="space-y-2">
                <div className="rounded p-2" style={{ background: "var(--gd-bg-3)" }}>
                  <div className="text-xs" style={{ color: "var(--gd-text-2)" }}>پله بعدی: {(s.next_tranche_pct * 100).toFixed(0)}٪ = {fmt(s.next_tranche_amount)} تومان</div>
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
              <td className={`p-3 text-left font-mono ${t.pnl_irt >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {t.pnl_irt ? (t.pnl_irt >= 0 ? "+" : "") + fmt(t.pnl_irt) : "—"}
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
