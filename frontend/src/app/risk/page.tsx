"use client";

/**
 * `/risk` — the user's own exposure, read from `/api/v1/risk`.
 *
 * This page used to render eight invented metrics, four invented alerts dated ۱۴۰۳, five
 * invented limits and a `Math.sin` "drawdown curve", all as `DEFAULT_*` fallbacks behind
 * requests to endpoints that did not exist. None of it described anybody's portfolio. There
 * are no fallbacks now: the server returns either a number with the window it came from, or
 * `unknown` with the reason, and the page shows exactly that.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import DrawdownChart from "@/components/charts/DrawdownChart";

type RiskState = "ok" | "warning" | "danger" | "unknown";

interface RiskMetric {
  key: string;
  label: string;
  unit: string;
  state: RiskState;
  value: number | null;
  basis: string;
  note: string;
}

interface RiskAlert {
  rule: string;
  severity: "low" | "medium" | "high";
  symbol: string | null;
  message: string;
}

interface RiskLimit {
  type: string;
  label: string;
  limit: number;
  unit: string;
  current: number | null;
  status: "ok" | "warning" | "exceeded" | "unknown";
}

interface DrawdownPoint {
  index: number;
  drawdown: number;
  date: string;
}

interface RiskSummary {
  state: "OK" | "NO_PORTFOLIO";
  portfolios: { id: string; name: string; initial_capital: number; current_value: number }[];
  metrics: RiskMetric[];
  drawdown: DrawdownPoint[];
  alerts: RiskAlert[];
  limits: RiskLimit[];
  note: string;
}

const STATE_TEXT: Record<RiskState, string> = {
  ok: "text-accent-emerald",
  warning: "text-accent-amber",
  danger: "text-accent-rose",
  unknown: "text-surface-400",
};

const STATE_BG: Record<RiskState, string> = {
  ok: "bg-accent-emerald/10",
  warning: "bg-accent-amber/10",
  danger: "bg-accent-rose/10",
  unknown: "bg-surface-800/40",
};

const DOT: Record<RiskState, string> = {
  ok: "bg-accent-emerald",
  warning: "bg-accent-amber",
  danger: "bg-accent-rose",
  unknown: "bg-surface-600",
};

const LIMIT_TEXT: Record<RiskLimit["status"], string> = {
  ok: "text-accent-emerald",
  warning: "text-accent-amber",
  exceeded: "text-accent-rose",
  unknown: "text-surface-400",
};

const RULE_LABEL: Record<string, string> = {
  stop_loss: "عبور از حد ضرر",
  drawdown: "عبور از حد افت",
  concentration: "تمرکز بیش از حد",
  daily_loss: "زیان بیش از حد مجاز",
};

const TABS = [
  { id: "metrics", label: "شاخص‌های ریسک", icon: "analytics" },
  { id: "alerts", label: "هشدارها", icon: "warning" },
  { id: "limits", label: "حد ریسک", icon: "shield" },
] as const;

const nf = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 });
const show = (value: number) => nf.format(Math.round(value * 100) / 100);

async function loadSummary(): Promise<RiskSummary> {
  const res = await apiGet<{ success?: boolean; data?: RiskSummary }>("/risk/");
  if (!res?.data) throw new Error("پاسخ برنامه قابل خواندن نبود");
  return res.data;
}

export default function RiskPage() {
  const [activeTab, setActiveTab] = useState<"metrics" | "alerts" | "limits">("metrics");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["risk-summary"],
    queryFn: loadSummary,
    staleTime: 60_000,
    retry: 1,
  });

  const metrics = data?.metrics ?? [];
  const alerts = data?.alerts ?? [];
  const limits = data?.limits ?? [];
  const drawdown = data?.drawdown ?? [];
  const noPortfolio = data?.state === "NO_PORTFOLIO";

  return (
    <AppLayout title="مدیریت ریسک" subtitle="شاخص‌ها، هشدارها و حدها — همگی از پرتفوی ذخیره‌شدهٔ خودتان">
      <div className="flex gap-2 mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-primary-600/20 text-primary-400"
                : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
            }`}
          >
            <span className="material-icons text-sm align-middle ml-1">{tab.icon}</span>
            {tab.label}
            {tab.id === "alerts" && alerts.length > 0 && (
              <span className="mr-1 px-1.5 py-0.5 text-xs bg-accent-rose/20 text-accent-rose rounded-full">
                {show(alerts.length)}
              </span>
            )}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4, 5, 6, 7].map((i) => (
            <Skeleton key={i} className="h-32 w-full rounded-xl" />
          ))}
        </div>
      )}

      {!isLoading && isError && (
        <Card title="دادهٔ ریسک خوانده نشد" subtitle="/api/v1/risk پاسخ نداد" className="mb-6">
          <p className="text-xs text-surface-400 mb-3">
            {error instanceof Error ? error.message : "خطای نامشخص"} — به‌جای آن عددی ساخته نمی‌شود.
          </p>
          <button
            onClick={() => void refetch()}
            className="px-3 py-1.5 text-xs rounded-lg border border-surface-700 text-surface-300 hover:bg-surface-800"
          >
            تلاش دوباره
          </button>
        </Card>
      )}

      {!isLoading && !isError && noPortfolio && (
        <Card title="پرتفویی ثبت نشده است" subtitle="برای محاسبهٔ ریسک، موقعیت لازم است" className="mb-6">
          <p className="text-xs text-surface-400 leading-relaxed">
            سابقهٔ قیمت‌ها در برنامه هست، ولی هیچ موقعیتی به نام شما ثبت نشده است؛ به همین دلیل هیچ‌کدام
            از شاخص‌های پایین عدد ندارد. با ثبت پرتفوی، همان شاخص‌ها از همان داده‌ها محاسبه می‌شوند.
          </p>
          <Link
            href="/portfolio"
            className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 text-xs rounded-lg bg-primary-600 text-white hover:bg-primary-500"
          >
            <span className="material-icons text-sm">add</span>
            رفتن به پرتفوی
          </Link>
        </Card>
      )}

      {activeTab === "metrics" && !isLoading && !isError && (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {metrics.map((m) => (
              <Card key={m.key} className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-surface-400">{m.label}</span>
                  <span className={`w-2 h-2 rounded-full ${DOT[m.state]}`} />
                </div>
                <div className={`text-2xl font-bold font-mono ${STATE_TEXT[m.state]}`}>
                  {m.value === null ? "—" : `${show(Math.abs(m.value))}${m.unit === "٪" ? "٪" : ""}`}
                </div>
                <p className="text-[11px] text-surface-500 mt-2 leading-relaxed">
                  {m.state === "unknown" ? m.note || "قابل محاسبه نیست" : m.basis}
                </p>
                {m.state !== "unknown" && m.note && (
                  <p className="text-[10px] text-surface-600 mt-1 leading-relaxed">{m.note}</p>
                )}
              </Card>
            ))}
          </div>

          <Card
            title="نمودار افت"
            subtitle={
              drawdown.length
                ? "فاصله تا سقف ارزش پرتفوی، بر پایهٔ قیمت‌های بسته‌شده"
                : "داده‌ای برای این نمودار نیست"
            }
            className="mb-6"
          >
            {drawdown.length > 1 ? (
              <div className="h-64">
                <DrawdownChart data={drawdown} height={250} />
              </div>
            ) : (
              <p className="text-xs text-surface-500 py-10 text-center">
                {noPortfolio
                  ? "با ثبت موقعیت‌ها این نمودار از ارزش روزانهٔ واقعی پرتفوی شما ساخته می‌شود."
                  : "روزهای مشترک بین نمادهای شما برای ساختن منحنی کافی نیست؛ تاریخ‌ها حدس زده نمی‌شوند."}
              </p>
            )}
          </Card>

          <button
            onClick={() => setActiveTab("alerts")}
            className="glass-card p-4 text-left hover:border-accent-amber transition-colors w-full sm:max-w-md"
          >
            <div className="flex items-center gap-3">
              <span className="w-10 h-10 rounded-lg bg-accent-amber/10 flex items-center justify-center">
                <span className="material-icons text-accent-amber">history</span>
              </span>
              <div>
                <div className="text-sm font-medium text-surface-200">عبورها از حد ریسک</div>
                <div className="text-xs text-surface-500">مشاهدهٔ هشدارهای فعلی</div>
              </div>
            </div>
          </button>
        </>
      )}

      {activeTab === "alerts" && !isLoading && !isError && (
        <Card title="هشدارهای ریسک" subtitle="عبور از حدهای خودِ برنامه — این فهرست پیامی ارسال نمی‌کند">
          {alerts.length === 0 ? (
            <p className="text-xs text-surface-500 py-6 text-center">
              هیچ موقعیتی از هیچ حدی عبور نکرده است — یا پرتفویی ثبت نشده است.
            </p>
          ) : (
            <div className="space-y-3">
              {alerts.map((alert, i) => {
                const state: RiskState =
                  alert.severity === "high" ? "danger" : alert.severity === "medium" ? "warning" : "ok";
                return (
                  <div
                    key={`${alert.rule}-${alert.symbol ?? "portfolio"}-${i}`}
                    className="flex items-center gap-4 p-4 rounded-lg bg-surface-800/20"
                  >
                    <span className={`w-10 h-10 rounded-full flex items-center justify-center ${STATE_BG[state]}`}>
                      <span className={`material-icons ${STATE_TEXT[state]}`}>
                        {alert.severity === "high" ? "error" : "warning"}
                      </span>
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-surface-200">
                          {RULE_LABEL[alert.rule] ?? alert.rule}
                        </span>
                        {alert.symbol && <span className="text-xs text-surface-400">{alert.symbol}</span>}
                      </div>
                      <p className="text-xs text-surface-400 mt-1">{alert.message}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      )}

      {activeTab === "limits" && !isLoading && !isError && (
        <Card title="حد ریسک" subtitle="خط‌مشی برنامه در برابر مقدار اندازه‌گرفته‌شده">
          <div className="space-y-4">
            {limits.map((limit) => {
              const measured = limit.current !== null;
              const current = limit.current ?? 0;
              const percentage = measured ? (Math.abs(current) / limit.limit) * 100 : 0;
              return (
                <div key={limit.type} className="p-4 rounded-lg bg-surface-800/20">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-surface-200">{limit.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-mono ${LIMIT_TEXT[limit.status]}`}>
                        {measured ? `${show(Math.abs(current))}${limit.unit}` : "اندازه گرفته نشد"}
                      </span>
                      <span className="text-surface-500">/</span>
                      <span className="text-sm font-mono text-surface-400">
                        {show(limit.limit)}
                        {limit.unit}
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        limit.status === "exceeded"
                          ? "bg-accent-rose"
                          : limit.status === "warning"
                            ? "bg-accent-amber"
                            : limit.status === "unknown"
                              ? "bg-surface-700"
                              : "bg-accent-emerald"
                      }`}
                      style={{ width: measured ? `${Math.min(percentage, 100)}%` : "0%" }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-surface-500">
                      {measured ? `${show(percentage)}٪ از حد استفاده شده` : "بدون موقعیتِ اندازه‌گیری‌شده"}
                    </span>
                    <span className={`text-xs ${LIMIT_TEXT[limit.status]}`}>
                      {limit.status === "exceeded"
                        ? "عبور از حد"
                        : limit.status === "warning"
                          ? "نزدیک به حد"
                          : limit.status === "unknown"
                            ? "مقدار فعلی نامشخص"
                            : "در محدوده مجاز"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </AppLayout>
  );
}
