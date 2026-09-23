"use client";

/**
 * Market microstructure, portfolio holdings, and performance tabs.
 *
 * The premium/discount reading is deliberately guarded: a صرف/کسر number is
 * only meaningful against a published (صدور/ابطال) NAV, so it is hidden — not
 * zeroed — when the NAV on the row is just a price proxy.
 */

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  useFundCandles,
  useFundDetail,
  useFundIntraday,
  useFundList,
  useFundRankings,
  useFundV2Backtest,
  useFundV2Holdings,
  useFundV2Score,
  usePortfolioDiffs,
  rankNum,
} from "@/lib/fund-queries";
import { Chip, DataTable, Empty, fmt, fmtBig, fmtDate, fmtPct, Loading, MiniMetric, Panel, SourceNote, Stat, StatGrid, toneText } from "@/components/funds/ui";
import {
  Activity,
  AlertCircle,
  CandlestickChart,
  Gauge,
  History,
  Tag,
  Trophy,
  Wallet,
} from "lucide-react";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});
const PieChartCard = dynamic(() => import("@/components/charts/PieChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});
const BarChartCard = dynamic(() => import("@/components/charts/BarChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});

export function premiumOf(f?: { nav?: number | null; nav_source?: string | null; price_last?: number | null } | null) {
  if (!f || f.nav_source !== "nav_record") return null;
  if (!f.nav || !f.price_last) return null;
  return ((f.price_last - f.nav) / f.nav) * 100;
}

const FLOW_LABELS: Record<string, { label: string; tone: "pos" | "neg" | "accent" | "muted" }> = {
  in: { label: "ورود پول", tone: "pos" },
  out: { label: "خروج پول", tone: "neg" },
  new: { label: "پوزیشن جدید", tone: "accent" },
  exited: { label: "خروج کامل", tone: "neg" },
  hold: { label: "بدون تغییر", tone: "muted" },
};

const HOLDING_TYPE_LABELS: Record<string, string> = {
  equity: "سهام",
  fixed_income: "اوراق با درآمد ثابت",
  deposit: "سپرده بانکی",
  gold: "طلا و کالا",
  derivative: "مشتقات",
  cash: "نقد",
  other: "سایر",
};

// ══════════════ گروه بازار ══════════════

export function QuoteTab({ symbol }: { symbol: string }) {
  const { data: f, isPending } = useFundDetail(symbol);
  if (isPending) return <Loading rows={4} />;
  if (!f) return <Empty text="تابلو بازنگشت" />;

  // A day range needs all three prices; without them there is no position to draw, and
  // centering the marker at 50% would invent one.
  const range = f.price_max !== null && f.price_min !== null ? f.price_max - f.price_min : null;
  const pos =
    range !== null && range > 0 && f.price_last !== null && f.price_min !== null
      ? Math.max(0, Math.min(100, ((f.price_last - f.price_min) / range) * 100))
      : null;
  const premium = premiumOf(f);

  return (
    <div className="space-y-4">
      <Panel title="تابلوی معاملات" desc={`آخرین وضعیت معاملاتی${f.time ? ` — ساعت ${f.time}` : ""}`}>
        <StatGrid cols={5}>
          <Stat label="قیمت آخرین" value={fmt(f.price_last)} tone="accent" icon={Tag} />
          <Stat label="قیمت دیروز" value={fmt(f.price_yesterday)} />
          <Stat label="قیمت پایانی" value={fmt(f.price_close)} />
          <Stat label="تغییر NAV" value={fmtPct(f.nav_change_pct)} tone={f.nav_change_pct === null ? "muted" : f.nav_change_pct >= 0 ? "pos" : "neg"} sub={fmt(f.nav_change)} />
          <Stat
            label="صرف / کسر"
            value={premium === null ? "—" : fmtPct(premium)}
            tone={premium === null ? "muted" : premium >= 0 ? "pos" : "neg"}
            sub={premium === null ? "NAV رسمی موجود نیست" : "قیمت به‌ازای NAV صدور/ابطال"}
          />
        </StatGrid>

        <div className="mt-5">
          <div className="flex items-center justify-between text-[10px] text-surface-500 mb-1">
            <span dir="ltr">{fmt(f.price_min)}</span>
            <span>بازه نوسان روز</span>
            <span dir="ltr">{fmt(f.price_max)}</span>
          </div>
          <div className="relative h-2 bg-surface-700/70 rounded-full">
            <div className="absolute inset-y-0 right-0 rounded-full bg-gradient-to-l from-accent-rose/50 via-accent-amber/40 to-accent-emerald/50 w-full" />
            {pos !== null && (
              <div
                className="absolute -top-1 w-3 h-4 rounded-sm bg-primary-300 shadow-lg shadow-primary-500/40 transition-all"
                style={{ right: `calc(${pos}% - 6px)` }}
                title={`قیمت آخرین در ${pos.toFixed(0)}٪ بازه روز`}
              />
            )}
          </div>
          <p className="text-[10px] text-surface-600 mt-1">
            {pos === null
              ? "بازه نوسان امروز از داده‌های معاملاتی خوانده نشده است."
              : "هرچه نشانگر به انتهای بازه نزدیک‌تر باشد، معامله در قیمت‌های بالاترِ دامنه نوسان انجام شده است."}
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          <MiniMetric label="حجم معاملات" value={fmtBig(f.trade_volume)} />
          <MiniMetric label="ارزش معاملات" value={fmtBig(f.trade_value)} />
          <MiniMetric label="تعداد معاملات" value={fmt(f.trade_count)} />
          <MiniMetric label="حجم مبنا" value={fmt(f.base_volume)} />
        </div>
        <SourceNote>
          <code>/funds/{symbol}</code> — اسنپ‌شات BrsApi؛ NAV وقتی برچسب «واقعی» می‌گیرد که رکورد صدور/ابطال برای همان
          تاریخ موجود باشد.
        </SourceNote>
      </Panel>

      <Panel title="ساختار مالکان واحد" desc="تفکیک خرید و فروش بین دو گروه حقیقی و حقوقی — منبع تشخیص فشار نقدینگی">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="خرید حقیقی" value={fmtBig(f.buy_real_volume)} tone="pos" />
          <Stat label="فروش حقیقی" value={fmtBig(f.sell_real_volume)} tone="neg" />
          <Stat label="خرید حقوقی" value={fmtBig(f.buy_legal_volume)} tone="pos" />
          <Stat label="فروش حقوقی" value={fmtBig(f.sell_legal_volume)} tone="neg" />
        </div>
        <div className="mt-4">
          <FlowBar label="حقیقی" buy={f.buy_real_volume} sell={f.sell_real_volume} />
          <FlowBar label="حقوقی" buy={f.buy_legal_volume} sell={f.sell_legal_volume} />
        </div>
      </Panel>
    </div>
  );
}

function FlowBar({ label, buy, sell }: { label: string; buy: number | null; sell: number | null }) {
  // Without both sides there is no split to draw: 50/50 and «خالص ورود ۰» were both readings
  // invented out of an unread order book.
  if (buy === null || sell === null) {
    return (
      <div className="mb-3">
        <div className="flex items-center justify-between text-[10px] text-surface-500 mb-1">
          <span>گروه {label}</span>
          <span className="text-surface-600">تفکیک خرید/فروش خوانده نشده</span>
        </div>
        <div className="h-2.5 rounded-full bg-surface-700/70" />
      </div>
    );
  }
  const total = buy + sell;
  const buyPct = total ? (buy / total) * 100 : 50;
  const net = buy - sell;
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-[10px] text-surface-500 mb-1">
        <span>گروه {label}</span>
        <span className={toneText(net === 0 ? "muted" : net > 0 ? "pos" : "neg")}>
          {net === 0 ? "خالص صفر" : `خالص ${net > 0 ? "ورود" : "خروج"} ${fmtBig(Math.abs(net))}`}
        </span>
      </div>
      <div className="flex h-2.5 rounded-full overflow-hidden bg-surface-700">
        <div className="bg-accent-emerald/80 transition-all" style={{ width: `${buyPct}%` }} />
        <div className="bg-accent-rose/80 flex-1" />
      </div>
    </div>
  );
}

export function TicksTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundIntraday(symbol);
  const pack = data?.symbols?.[symbol];
  const ticks = pack?.ticks ?? [];

  if (isPending) return <Loading rows={5} />;
  if (pack?.error) return <Empty text="خطا در دریافت تیک‌ها" hint={pack.error} icon={AlertCircle} />;
  if (!ticks.length)
    return <Empty text="تیکی برای آخرین روز ثبت‌شده موجود نیست" hint="ممکن است صندوق در آخرین روز معاملاتی معامله نشده باشد." icon={Activity} />;

  const s = pack!.summary;
  return (
    <div className="space-y-4">
      <Panel title="ریز معاملات (تیک)" desc={`${ticks.length} تیک در ${pack!.trade_date ?? "آخرین روز"} — به ترتیب زمان`}>
        {s && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <MiniMetric label="باز/بسته شد" value={fmt(s.first_price)} sub={`تا ${s.first_time}`} />
            <MiniMetric label="آخرین معامله" value={fmt(s.last_price)} sub={`ساعت ${s.last_time}`} tone="accent" />
            <MiniMetric label="کمینه / بیشینه" value={`${fmt(s.price_min)} / ${fmt(s.price_max)}`} />
            <MiniMetric label="جمع حجم و ارزش" value={fmtBig(s.volume)} sub={fmtBig(s.value)} />
          </div>
        )}
        <DataTable
          rows={ticks.slice(-300).reverse() as unknown as Record<string, unknown>[]}
          columns={[
            { key: "time", label: "ساعت", render: (r) => <span dir="ltr">{String(r.time)}</span> },
            { key: "price", label: "قیمت", render: (r) => <span dir="ltr">{fmt(r.price, 0)}</span> },
            { key: "volume", label: "حجم", render: (r) => <span dir="ltr">{fmt(r.volume)}</span> },
            { key: "value", label: "ارزش", render: (r) => <span dir="ltr">{fmtBig(Number(r.price ?? 0) * Number(r.volume ?? 0))}</span> },
            {
              key: "canceled",
              label: "کنسل",
              render: (r) => (r.canceled ? <Chip label="کنسل‌شده" tone="warn" /> : <span className="text-surface-600">—</span>),
            },
          ]}
          maxHeight={420}
          dense
        />
        <SourceNote>
          تیک‌های کنسل‌شده به‌صورت پیش‌فرض حذف می‌شوند؛ برای دیدن آن‌ها از پارامتر
          <code>include_canceled=true</code> استفاده می‌شود.
        </SourceNote>
      </Panel>
    </div>
  );
}

export function CandlesTab({ symbol }: { symbol: string }) {
  const [bucket, setBucket] = useState(5);
  const { data, isPending } = useFundCandles(symbol, bucket);
  const pack = data?.symbols?.[symbol];
  const candles = useMemo(() => pack?.candles ?? [], [pack]);

  const chart = useMemo(
    () =>
      candles.map((c) => {
        const close = Number(c.close ?? c.val ?? 0) / (Number(c.vol ?? 0) || 1);
        return { date: String(c.m ?? c.time ?? ""), value: Number.isFinite(close) && close > 0 ? close : Number(c.close ?? 0) };
      }),
    [candles]
  );

  return (
    <Panel
      title="کندل درون‌روز"
      desc="تجمیع تیک‌ها در سطل‌های زمانی — محاسبه در دیتابیس انجام می‌شود."
      actions={
        <div className="flex items-center gap-1">
          {[1, 5, 15, 30].map((m) => (
            <button
              key={m}
              onClick={() => setBucket(m)}
              className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-colors ${
                bucket === m ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {m} دقیقه
            </button>
          ))}
        </div>
      }
    >
      {isPending ? (
        <Loading rows={4} />
      ) : candles.length ? (
        <>
          <p className="text-[11px] text-surface-500 mb-2">
            روز معاملاتی <span dir="ltr">{fmtDate(pack!.trade_date)}</span> — {candles.length} کندل
          </p>
          <AreaChartCard
            title=""
            data={chart}
            dataKey="value"
            height={260}
            strokeColor="#06b6d4"
            gradientId="fundCandleGrad"
            primaryLabel="قیمت"
            showAverage
            showMinMax
          />
          <div className="mt-4">
            <DataTable
              rows={candles as unknown as Record<string, unknown>[]}
              columns={[
                { key: "m", label: "ساعت", render: (r) => <span dir="ltr">{String(r.m ?? r.time ?? "—")}</span> },
                { key: "open", label: "ابتدا", render: (r) => <span dir="ltr">{fmt(r.open, 0)}</span> },
                { key: "high", label: "بیشینه", render: (r) => <span dir="ltr">{fmt(r.high, 0)}</span> },
                { key: "low", label: "کمینه", render: (r) => <span dir="ltr">{fmt(r.low, 0)}</span> },
                { key: "close", label: "بسته", render: (r) => <span dir="ltr">{fmt(r.close, 0)}</span> },
                { key: "vol", label: "حجم", render: (r) => <span dir="ltr">{fmt(r.vol)}</span> },
                { key: "n", label: "تیک", render: (r) => <span dir="ltr">{fmt(r.n)}</span> },
              ]}
              maxHeight={300}
              dense
            />
          </div>
        </>
      ) : (
        <Empty text="کندلی ساخته نشد" hint="برای این نماد تیک معاملاتی در دسترس نیست." icon={CandlestickChart} />
      )}
      <SourceNote>
        <code>/funds/intraday/candles?symbols={symbol}&interval_minutes={bucket}</code>
      </SourceNote>
    </Panel>
  );
}

// ══════════════ گروه سبد دارایی ══════════════

export function HoldingsTab({ symbol }: { symbol: string }) {
  const [type, setType] = useState("all");
  const { data, isPending } = useFundV2Holdings(symbol);
  const holdings = useMemo(() => data?.holdings ?? [], [data]);
  const types = useMemo(() => Array.from(new Set(holdings.map((h) => String(h.holding_type ?? "other")))), [holdings]);
  const rows = useMemo(() => (type === "all" ? holdings : holdings.filter((h) => String(h.holding_type) === type)), [holdings, type]);

  if (isPending) return <Loading rows={5} />;
  if (!holdings.length)
    return (
      <Empty
        text="ریز دارایی از کدال دریافت نشده"
        hint="ترکیب دارایی به‌صورت JIT از گزارش ماهانه کدال خوانده و کش می‌شود."
        icon={Wallet}
      />
    );

  return (
    <Panel
      title="ریز دارایی صندوق"
      desc={`${holdings.length} ردیف از آخرین گزارش رسمی — با فیلتر نوع دارایی`}
      actions={
        <div className="flex gap-1 flex-wrap">
          <FilterPill label="همه" active={type === "all"} onClick={() => setType("all")} />
          {types.map((t) => (
            <FilterPill key={t} label={HOLDING_TYPE_LABELS[t] ?? t} active={type === t} onClick={() => setType(t)} />
          ))}
        </div>
      }
    >
      <DataTable
        rows={rows as unknown as Record<string, unknown>[]}
        columns={[
          { key: "instrument_symbol", label: "نماد", render: (r) => <span className="font-bold text-surface-100">{String(r.instrument_symbol ?? "—")}</span> },
          { key: "instrument_name", label: "نام", render: (r) => <span className="text-surface-400">{String(r.instrument_name ?? "—")}</span> },
          { key: "holding_type", label: "نوع", render: (r) => <Chip label={HOLDING_TYPE_LABELS[String(r.holding_type)] ?? String(r.holding_type)} tone="muted" /> },
          { key: "quantity", label: "تعداد", render: (r) => <span dir="ltr">{fmtBig(r.quantity)}</span> },
          { key: "market_value", label: "ارزش", render: (r) => <span dir="ltr">{fmtBig(r.market_value)}</span> },
          { key: "weight_pct", label: "وزن", render: (r) => <span dir="ltr" className="text-primary-300 font-bold">{fmt(r.weight_pct, 2)}٪</span> },
        ]}
        maxHeight={460}
      />
      <SourceNote>
        <code>/funds/v2/{symbol}/holdings</code> — وزن‌ها از گزارش ترکیب دارایی کدال؛ به‌همین دلیل با پایان ماه
        تغییر می‌کنند و در طول ماه ثابت‌اند.
      </SourceNote>
    </Panel>
  );
}

function FilterPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-colors ${
        active ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
      }`}
    >
      {label}
    </button>
  );
}

export function CompositionTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundV2Holdings(symbol);
  const holdings = useMemo(() => data?.holdings ?? [], [data]);

  const byType = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const h of holdings) {
      const label = HOLDING_TYPE_LABELS[String(h.holding_type ?? "other")] ?? String(h.holding_type ?? "other");
      acc[label] = (acc[label] ?? 0) + Number(h.market_value ?? 0);
    }
    const colors = ["#10b981", "#06b6d4", "#f59e0b", "#eab308", "#a78bfa", "#64748b", "#f43f5e"];
    return Object.entries(acc)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value], i) => ({ name, value, color: colors[i % colors.length] }));
  }, [holdings]);

  const top = useMemo(
    () =>
      [...holdings]
        .filter((h) => h.holding_type === "equity")
        .sort((a, b) => Number(b.weight_pct ?? 0) - Number(a.weight_pct ?? 0))
        .slice(0, 12),
    [holdings]
  );

  if (isPending) return <Loading rows={4} />;
  if (!byType.length) return <Empty text="ترکیب دارایی موجود نیست" />;

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-4">
        <Panel title="ترکیب بر اساس نوع دارایی" desc="سهم ارزش هر طبقه از کل پرتفوی">
          <PieChartCard title="" data={byType} />
        </Panel>
        <Panel title="بزرگ‌ترین دارایی‌ها" desc="۱۲ دارایی برتر از نظر وزن">
          <div className="space-y-1.5">
            {top.map((h, i) => (
              <div key={`${String(h.instrument_symbol)}-${i}`} className="flex items-center gap-2 bg-surface-800/40 rounded-lg px-3 py-2">
                <span className="text-[10px] font-mono text-surface-600 w-5">{i + 1}</span>
                <span className="font-bold text-surface-100 text-xs w-20">{String(h.instrument_symbol ?? "—")}</span>
                <span className="flex-1 text-[10px] text-surface-500 truncate">{String(h.instrument_name ?? "")}</span>
                <span className="w-24 h-1.5 bg-surface-700 rounded-full overflow-hidden">
                  <span className="block h-full bg-primary-500" style={{ width: `${Math.min(100, Number(h.weight_pct ?? 0) * 2)}%` }} />
                </span>
                <span className="font-mono text-[11px] text-primary-300" dir="ltr">
                  {fmt(h.weight_pct, 2)}٪
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="توزیع وزن دارایی‌ها" desc="وزن درصدی ۱۵ دارایی اول — برای دیدن تمرکز و ریسک تک‌دارایی">
        <BarChartCard
          title=""
          data={top.slice(0, 15).map((h) => ({ date: String(h.instrument_symbol ?? "—"), value: Number(h.weight_pct ?? 0) }))}
          height={230}
          valueLabel="وزن ٪"
        />
      </Panel>
    </div>
  );
}

export function DiffsTab({ symbol }: { symbol: string }) {
  const { data, isPending } = usePortfolioDiffs(symbol);
  const diffs = useMemo(() => data?.diffs ?? [], [data]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const d of diffs) c[String(d.flow_direction ?? "hold")] = (c[String(d.flow_direction ?? "hold")] ?? 0) + 1;
    return c;
  }, [diffs]);

  if (isPending) return <Loading rows={4} />;
  if (!diffs.length)
    return <Empty text="تغییر وزنی بین دو دوره ثبت نشده" hint="برای محاسبه ورود/خروج پول به حداقل دو گزارش ماهانه متوالی نیاز است." />;

  return (
    <Panel title="تغییرات پرتفوی بین دو دوره" desc="وزن هر دارایی در گزارش فعلی منهای گزارش قبلی — تشخیص جهت پول مدیر صندوق">
      <div className="flex gap-2 flex-wrap mb-3">
        {Object.entries(counts).map(([k, v]) => {
          const meta = FLOW_LABELS[k] ?? { label: k, tone: "muted" as const };
          return <Chip key={k} label={`${meta.label}: ${v.toLocaleString("fa-IR")}`} tone={meta.tone} />;
        })}
      </div>
      <DataTable
        rows={diffs as unknown as Record<string, unknown>[]}
        columns={[
          { key: "instrument_symbol", label: "دارایی", render: (r) => <span className="font-bold text-surface-100">{String(r.instrument_symbol ?? "—")}</span> },
          { key: "period", label: "دوره", render: (r) => <span dir="ltr">{fmtDate(r.period)}</span> },
          {
            key: "weight_change_pct",
            label: "تغییر وزن",
            render: (r) => (
              <span dir="ltr" className={Number(r.weight_change_pct ?? 0) >= 0 ? "text-accent-emerald font-bold" : "text-accent-rose font-bold"}>
                {fmtPct(Number(r.weight_change_pct))}
              </span>
            ),
          },
          {
            key: "flow_direction",
            label: "جریان",
            render: (r) => {
              const meta = FLOW_LABELS[String(r.flow_direction ?? "hold")] ?? FLOW_LABELS.hold;
              return <Chip label={meta.label} tone={meta.tone} />;
            },
          },
        ]}
        maxHeight={430}
      />
      <SourceNote>
        <code>/funds/v2/portfolio-diffs?fund_id={symbol}</code> — مقایسه گزارش‌های کدال، نه تراکنش‌های روز.
      </SourceNote>
    </Panel>
  );
}

// ══════════════ گروه عملکرد ══════════════

export function ScoreTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundV2Score(symbol);
  if (isPending) return <Loading rows={4} />;
  if (!data || data.total === undefined)
    return <Empty text="امتیاز کمی محاسبه نشده" hint={`نقطه NAV کافی نیست: ${data?.points_available ?? 0}`} icon={Gauge} />;

  const m = data.metrics ?? {};
  const comp = data.components ?? {};

  return (
    <div className="space-y-4">
      <Panel title="امتیاز کمی و اجزای آن" desc={`ساخته‌شده از ${data.points_used ?? data.points_available ?? 0} نقطه NAV`}>
        <div className="flex items-center gap-4 mb-4">
          <div className="relative w-24 h-24 shrink-0">
            <svg viewBox="0 0 100 100" className="w-24 h-24 -rotate-90">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" className="text-surface-700" strokeWidth="10" />
              <circle
                cx="50"
                cy="50"
                r="42"
                fill="none"
                stroke={data.total >= 70 ? "#10b981" : data.total >= 45 ? "#f59e0b" : "#f43f5e"}
                strokeWidth="10"
                strokeLinecap="round"
                strokeDasharray={`${(data.total / 100) * 264} 264`}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center font-mono text-xl font-black text-surface-100">
              {data.total.toFixed(0)}
            </span>
          </div>
          <div className="flex-1 grid grid-cols-2 gap-2">
            <MiniMetric label="بازدهی ۱ ساله" value={m.total_return_1y_pct != null ? fmtPct(m.total_return_1y_pct) : undefined} tone={(m.total_return_1y_pct ?? 0) >= 0 ? "pos" : "neg"} />
            <MiniMetric label="نوسان سالانه" value={m.volatility_annual_pct != null ? `${m.volatility_annual_pct.toFixed(1)}٪` : undefined} />
            <MiniMetric label="بتا" value={m.beta != null ? m.beta.toFixed(2) : undefined} />
            <MiniMetric label="خطای ردیابی" value={m.tracking_error_pct != null ? `${m.tracking_error_pct.toFixed(2)}٪` : undefined} />
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniMetric label="شارپ" value={m.sharpe != null ? m.sharpe.toFixed(2) : undefined} />
          <MiniMetric label="سورتینو" value={m.sortino != null ? m.sortino.toFixed(2) : undefined} />
          <MiniMetric label="حداکثر افت" value={m.max_drawdown_pct != null ? `${m.max_drawdown_pct.toFixed(1)}٪` : undefined} tone="neg" />
          <MiniMetric label="کالمر" value={m.calmar != null ? m.calmar.toFixed(2) : undefined} />
        </div>
      </Panel>
      <Panel title="اجزای امتیاز" desc="وزن هر مؤلفه در امتیاز نهایی">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(comp).map(([k, v]) => (
            <MeterCell key={k} label={{ return: "بازدهی", risk: "ریسک", liquidity: "نقدشوندگی", stability: "ثبات" }[k] ?? k} value={Number(v)} />
          ))}
        </div>
      </Panel>
      <SourceNote>
        <code>/funds/v2/{symbol}/score</code> — متریک‌ها از سری NAV همان صندوق؛ آلفا نسبت به شاخص کل.
      </SourceNote>
    </div>
  );
}

function MeterCell({ label, value }: { label: string; value: number }) {
  const color = value >= 70 ? "#10b981" : value >= 45 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="bg-surface-800/40 rounded-lg p-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-surface-400">{label}</span>
        <span className="text-[11px] font-mono font-bold" style={{ color }} dir="ltr">
          {value.toFixed(0)}
        </span>
      </div>
      <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.max(0, Math.min(100, value))}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export function RankingsTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundRankings(100);
  const rows = data?.rankings ?? [];
  const mine = rows.find((r) => r.symbol === symbol);
  if (isPending) return <Loading rows={6} />;
  if (!rows.length) return <Empty text="رتبه‌بندی هنوز تولید نشده" hint="پس از اولین چرخه امتیازدهی دوره‌ای فعال می‌شود." icon={Trophy} />;

  return (
    <Panel
      title="رتبه‌بندی صندوق‌ها"
      desc="بر پایه آخرین امتیاز هر صندوق — ردیف این صندوق مشخص شده است"
      actions={mine ? <Chip label={`رتبه ${mine.rank} از ${rows.length}`} tone="accent" /> : <Chip label="خارج از ۱۰۰ نفر برتر" tone="muted" />}
    >
      <DataTable
        rows={rows as unknown as Record<string, unknown>[]}
        highlight={(r) => r.symbol === symbol}
        columns={[
          { key: "rank", label: "#", render: (r) => <span className="font-mono text-primary-300" dir="ltr">{Number(r.rank)}</span> },
          {
            key: "symbol",
            label: "صندوق",
            render: (r) =>
              r.symbol ? (
                <Link href={`/funds/${encodeURIComponent(String(r.symbol))}`} className="hover:text-primary-300 transition-colors">
                  <span className="font-bold text-surface-100">{String(r.symbol)}</span>
                  <span className="text-surface-500 text-[10px] mr-1.5">{String(r.name ?? "")}</span>
                </Link>
              ) : (
                "—"
              ),
          },
          { key: "fund_type", label: "نوع", render: (r) => <Chip label={String(r.fund_type ?? "—")} tone="muted" /> },
          { key: "total_score", label: "امتیاز", render: (r) => <span dir="ltr" className="font-bold">{fmt(r.total_score, 1)}</span> },
          { key: "sharpe", label: "شارپ", render: (r) => <span dir="ltr">{fmt(r.sharpe, 2)}</span> },
          { key: "max_drawdown", label: "حداکثر افت", render: (r) => <span dir="ltr" className="text-accent-rose">{fmt(r.max_drawdown, 1)}٪</span> },
          { key: "score_date", label: "تاریخ", render: (r) => <span dir="ltr">{fmtDate(r.score_date)}</span> },
        ]}
        maxHeight={460}
      />
    </Panel>
  );
}

export function PeersTab({ symbol }: { symbol: string }) {
  const { data: detail } = useFundDetail(symbol);
  const { data: list, isPending } = useFundList();
  const myType = detail?.fund_type;

  const peers = useMemo(() => {
    if (!list?.items || !myType) return [];
    return list.items.filter((f) => f.fund_type === myType).sort((a, b) => rankNum(b.market_value) - rankNum(a.market_value));
  }, [list, myType]);

  if (isPending) return <Loading rows={5} />;
  if (!myType) return <Empty text="نوع این صندوق مشخص نیست" hint="بدون نوع، هم‌گروهی قابل تعریف نیست." />;
  if (!peers.length) return <Empty text="هم‌گروهی یافت نشد" />;

  return (
    <Panel title="صندوق‌های هم‌گروه" desc={`${peers.length} صندوق از نوع «${myType}» — رتبه‌بندی بر اساس ارزش بازار`}>
      <DataTable
        rows={peers.slice(0, 30) as unknown as Record<string, unknown>[]}
        highlight={(r) => r.symbol === symbol}
        columns={[
          {
            key: "symbol",
            label: "نماد",
            render: (r) => (
              <Link href={`/funds/${encodeURIComponent(String(r.symbol))}`} className="font-bold text-surface-100 hover:text-primary-300 transition-colors">
                {String(r.symbol)}
              </Link>
            ),
          },
          { key: "name", label: "نام", render: (r) => <span className="text-surface-400">{String(r.name ?? "—")}</span> },
          { key: "market_value", label: "ارزش بازار", render: (r) => <span dir="ltr">{fmtBig(r.market_value)}</span> },
          { key: "nav", label: "NAV", render: (r) => <span dir="ltr">{fmt(r.nav)}</span> },
          {
            key: "nav_change_pct",
            label: "تغییر",
            render: (r) => (
              <span dir="ltr" className={Number(r.nav_change_pct) >= 0 ? "text-accent-emerald" : "text-accent-rose"}>
                {fmtPct(Number(r.nav_change_pct))}
              </span>
            ),
          },
          {
            key: "premium",
            label: "صرف/کسر",
            render: (r) => {
              const p = premiumOf(r as never);
              return p === null ? <span className="text-surface-600">—</span> : <span dir="ltr" className={p >= 0 ? "text-accent-emerald" : "text-accent-rose"}>{fmtPct(p)}</span>;
            },
          },
          { key: "trade_value", label: "ارزش معاملاتی", render: (r) => <span dir="ltr">{fmtBig(r.trade_value)}</span> },
        ]}
        maxHeight={430}
      />
      <SourceNote>
        ستون صرف/کسر فقط برای صندوق‌هایی عدد می‌دهد که NAV صدور/ابطال امروزشان ثبت شده باشد؛ بقیه عمداً خالی است.
      </SourceNote>
    </Panel>
  );
}

const STRATEGY_LABELS: Record<string, string> = {
  buy_hold: "خرید و نگهداری",
  dca_monthly: "میانگین‌گیری ماهانه",
  dip_buying: "خرید در افت",
};

export function BacktestTab({ symbol }: { symbol: string }) {
  const { data, isPending } = useFundV2Backtest(symbol);
  if (isPending) return <Loading rows={3} />;
  if (!data?.available || !data.strategies)
    return <Empty text="بک‌تست فعال نیست" hint="این تحلیل به حداقل ۳۰ نقطه NAV پیوسته نیاز دارد." icon={History} />;

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-3">
        {Object.entries(data.strategies).map(([key, s]) => (
          <div key={key} className="glass-card p-4">
            <p className="text-xs font-bold text-surface-100 mb-3">{STRATEGY_LABELS[key] ?? key}</p>
            <div className="space-y-2 text-[11px]">
              <RowLine label="سرمایه‌گذاری" value={fmtBig(s.total_invested)} />
              <RowLine label="ارزش نهایی" value={fmtBig(s.final_value)} tone={s.final_value >= s.total_invested ? "pos" : "neg"} />
              <RowLine label="بازدهی کل" value={fmtPct(s.total_return_pct)} tone={s.total_return_pct >= 0 ? "pos" : "neg"} />
              <RowLine label="بازدهی سالانه" value={s.annualized_return_pct != null ? fmtPct(s.annualized_return_pct) : "—"} />
              <RowLine label="حداکثر افت" value={`${s.max_drawdown_pct?.toFixed?.(1) ?? "—"}٪`} tone="neg" />
              <RowLine label="تعداد معامله" value={fmt(s.trade_count)} />
            </div>
          </div>
        ))}
      </div>
      <SourceNote>
        شبیه‌سازی با کارمزد واقعی و تقویم بازار ایران، بدون استفاده از داده آینده؛ بنابراین نتایج دوره‌هایی با صف
        خرید/فروش، خوش‌بینانه نیست.
      </SourceNote>
    </div>
  );
}

function RowLine({ label, value, tone = "default" }: { label: string; value: string; tone?: Parameters<typeof toneText>[0] }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-surface-500">{label}</span>
      <span className={`font-mono font-bold ${toneText(tone)}`} dir="ltr">
        {value}
      </span>
    </div>
  );
}
