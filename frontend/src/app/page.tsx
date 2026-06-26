"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import ClientOnly from "@/components/ClientOnly";
import { apiGet, safeExtractArray } from "@/lib/api";
import {
  generateMockNews,
  generateMockExperts,
  generateIndexHistory,
  generateVolumeData,
  generateSectorPerformance,
  generateSentimentHistory,
} from "@/lib/types";
import type { MarketStats, AIInsight, ChartDataPoint } from "@/lib/types";

// ── Debug Panel ──────────────────────────────────────
import DebugPanel from "@/components/DebugPanel";
import { useDebugLogs } from "@/hooks/useDebugLogs";

// ── Dynamic chart imports (ssr: false) ─────────
const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 280 }} />,
});
const BarChartCard = dynamic(() => import("@/components/charts/BarChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 200 }} />,
});
const PieChartCard = dynamic(() => import("@/components/charts/PieChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 200 }} />,
});
const SentimentChart = dynamic(() => import("@/components/charts/SentimentChart"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 200 }} />,
});

// ── Mock Data ──────────────────────────────────────
const MOCK_STATS: MarketStats = {
  marketCap: 8400000,
  totalVolume: 12456,
  totalTrades: 890123,
  indexValue: 2145678,
};

const MOCK_INSIGHTS: AIInsight[] = [
  { title: "روند صعودی پیش‌بینی شده", description: "مدل یادگیری ماشین با دقت ۸۷٪ پیش‌بینی می‌کند که قیمت فولاد در ۷ روز آینده ۵.۳٪ رشد خواهد کرد.", type: "positive", icon: "trending_up" },
  { title: "الگوی تکنیکال مثبت", description: "تشخیص الگوی کف دوگانه در نمودار روزانه که نشان‌دهنده احتمال رشد قیمت در کوتاه‌مدت است.", type: "positive", icon: "psychology" },
  { title: "تحلیل احساسات بازار", description: "احساسات بازار نسبت به هفته گذشته ۱۲٪ بهبود یافته و به محدوده مثبت وارد شده است.", type: "neutral", icon: "analytics" },
];

function formatNumber(n: number) {
  return n.toLocaleString("fa-IR");
}

const INDEX_DATA = generateIndexHistory(90);
const VOLUME_DATA = generateVolumeData(60);
const SECTOR_DATA = generateSectorPerformance();
const SENTIMENT_DATA = generateSentimentHistory(30);
const DEFAULT_NEWS = generateMockNews();
const DEFAULT_EXPERTS = generateMockExperts();

// ── Index Value Formatters ──────────────────────────
const indexFormatter = (v: number) => {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toString();
};

const volumeFormatter = (v: number) => {
  if (v >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(1)}T`;
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  return v.toLocaleString("fa-IR");
};

export default function DashboardPage() {
  const [indexRange, setIndexRange] = useState("3m");
  const [chartData, setChartData] = useState<ChartDataPoint[]>(INDEX_DATA);

  // ── Debug Hooks ──────────────────────────────────────
  const { logs, stats, addLog, clearLogs, isEnabled, toggleEnabled } = useDebugLogs();

  // ── Fetch news from backend (with debug) ────────────


const { data: news = DEFAULT_NEWS } = useQuery({
  queryKey: ["dashboard-news"],
  queryFn: async () => {
    const endpoint = "/news?page=1&page_size=3";
    addLog(endpoint, "loading");
    try {
      const res = await apiGet<any>(endpoint);
      const extracted = safeExtractArray(res);
      addLog(endpoint, "success", extracted);
      return extracted;
    } catch (error: any) {
      addLog(endpoint, "error", undefined, error.message);
      return DEFAULT_NEWS;
    }
  },
  refetchInterval: 60000,
  staleTime: 30000,
});

  // ── Period switcher for index chart ────────
  const handlePeriodChange = (period: string) => {
    setIndexRange(period);
    switch (period) {
      case "1w": setChartData(generateIndexHistory(7)); break;
      case "1m": setChartData(generateIndexHistory(30)); break;
      case "3m": setChartData(generateIndexHistory(90)); break;
      case "1y": setChartData(generateIndexHistory(250)); break;
      default: setChartData(generateIndexHistory(90));
    }
  };

  return (
    <AppLayout>
      {/* ── Top Row: Index Chart + News ──────── */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 15, marginBottom: 15 }}>
        {/* Main Index Chart with Recharts */}
        <AreaChartCard
          title="نمودار شاخص کل بورس"
          data={chartData}
          yAxisFormatter={indexFormatter}
          tooltipFormatter={(v) => `${v.toLocaleString("fa-IR")} واحد`}
          height={280}
          actions={
            <>
              <CardAction active={indexRange === "1w"} onClick={() => handlePeriodChange("1w")}>۱ هفته</CardAction>
              <CardAction active={indexRange === "1m"} onClick={() => handlePeriodChange("1m")}>۱ ماه</CardAction>
              <CardAction active={indexRange === "3m"} onClick={() => handlePeriodChange("3m")}>۳ ماه</CardAction>
              <CardAction active={indexRange === "1y"} onClick={() => handlePeriodChange("1y")}>۱ سال</CardAction>
            </>
          }
        />

        {/* News & Expert Opinions */}
        <Card
          title="اخبار و نظرات کارشناسان"
          actions={
            <>
              <CardAction active>همه</CardAction>
              <CardAction>اخبار</CardAction>
              <CardAction>نظرات</CardAction>
            </>
          }
        >
          <div className="news-container" style={{ maxHeight: 280 }}>
            <div className="news-section-title">اخبار بازار</div>
            {(Array.isArray(news) ? news.slice(0, 3) : []).map((item: any, i: number) => (
              <div key={item.id || i} className="news-item">
                <div className={`news-icon ${!item.sentiment || item.sentiment === "positive" ? "positive" : item.sentiment === "negative" ? "negative" : "neutral"}`}>
                  <span className="material-icons">
                    {item.sentiment === "positive" ? "trending_up" : item.sentiment === "negative" ? "trending_down" : "remove_circle_outline"}
                  </span>
                </div>
                <div className="news-content">
                  <div className="news-title">{item.title || "بدون عنوان"}</div>
                  <div className="news-source">{item.source || ""}</div>
                  <div className="news-time" suppressHydrationWarning>
                    <span className="material-icons" style={{ fontSize: 12 }}>access_time</span>
                    {item.published_at || item.date || ""}
                  </div>
                </div>
              </div>
            ))}
            <div className="news-section-title">نظرات کارشناسان</div>
            {DEFAULT_EXPERTS.slice(0, 2).map((expert) => (
              <div key={expert.id} className="expert-opinion">
                <div className="expert-avatar">{expert.avatar}</div>
                <div className="expert-content">
                  <div className="expert-header">
                    <div className="expert-name">{expert.name}</div>
                    <div className="news-time" suppressHydrationWarning>
                      <span className="material-icons" style={{ fontSize: 12 }}>access_time</span>
                      {expert.time}
                    </div>
                  </div>
                  <div className="expert-role">{expert.role}</div>
                  <div className="expert-opinion-text">
                    {expert.text}
                    {expert.symbols.map((s) => (
                      <span key={s} className="expert-symbol">{s}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ── Bottom Row: Volume + Sector + Stats ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 15, marginBottom: 15 }}>
        {/* Volume Bar Chart */}
        <BarChartCard
          title="حجم معاملات روزانه"
          data={VOLUME_DATA.slice(-20)}
          yAxisFormatter={volumeFormatter}
          tooltipFormatter={(v) => `${volumeFormatter(v)} ریال`}
          height={200}
        />

        {/* Sector Performance Donut */}
        <PieChartCard
          title="ترکیب صنایع بازار"
          data={SECTOR_DATA}
          height={200}
          innerRadius={40}
          outerRadius={70}
          valueFormatter={(v) => `${v.toFixed(0)}%`}
        />

        {/* Market Stats */}
        <Card title="آمار بازار">
          <div className="device-stats" style={{ height: 200 }}>
            <div className="device-stat">
              <div className="device-stat-title">ارزش بازار</div>
              <div className="device-stat-value">{formatNumber(MOCK_STATS.marketCap)}</div>
              <div className="device-stat-desc">میلیارد تومان</div>
              <div className="device-progress"><div className="device-progress-bar" style={{ width: "85%" }} /></div>
            </div>
            <div className="device-stat">
              <div className="device-stat-title">ارزش معاملات</div>
              <div className="device-stat-value">{formatNumber(MOCK_STATS.totalVolume)}</div>
              <div className="device-stat-desc">میلیارد تومان</div>
              <div className="device-progress"><div className="device-progress-bar" style={{ width: "72%" }} /></div>
            </div>
            <div className="device-stat">
              <div className="device-stat-title">تعداد معاملات</div>
              <div className="device-stat-value">{formatNumber(MOCK_STATS.totalTrades)}</div>
              <div className="device-stat-desc">معامله</div>
              <div className="device-progress"><div className="device-progress-bar" style={{ width: "68%" }} /></div>
            </div>
            <div className="device-stat">
              <div className="device-stat-title">شاخص کل</div>
              <div className="device-stat-value">{formatNumber(MOCK_STATS.indexValue)}</div>
              <div className="device-stat-desc">واحد</div>
              <div className="device-progress"><div className="device-progress-bar" style={{ width: "76%" }} /></div>
            </div>
          </div>
        </Card>
      </div>

      {/* ── Bottom Row 2: Top Symbols + Sentiment + AI Insights ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 15 }}>
        {/* Top Symbols Table */}
        <Card
          title="نمادهای برتر بازار"
          actions={
            <>
              <CardAction active>پربازدید</CardAction>
              <CardAction>پرمعامله</CardAction>
            </>
          }
        >
          <div style={{ overflow: "hidden" }}>
            <table className="symbols-table">
              <thead>
                <tr>
                  <th>نماد</th>
                  <th>قیمت</th>
                  <th>تغییر</th>
                  <th>حجم</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { symbol: "فولاد", price: "12,450", change: "+2.34%", isUp: true, volume: "5M" },
                  { symbol: "خودرو", price: "8,760", change: "-1.23%", isUp: false, volume: "3M" },
                  { symbol: "پترول", price: "23,890", change: "+3.45%", isUp: true, volume: "2M" },
                  { symbol: "بانک", price: "5,670", change: "0.00%", isUp: null, volume: "1.5M" },
                  { symbol: "کالا", price: "18,230", change: "+1.56%", isUp: true, volume: "1M" },
                  { symbol: "وغدیر", price: "19,450", change: "-2.10%", isUp: false, volume: "0.8M" },
                ].map((row) => (
                  <tr key={row.symbol}>
                    <td className="symbol">{row.symbol}</td>
                    <td className="value">{row.price}</td>
                    <td className={`value ${row.isUp === true ? "positive" : row.isUp === false ? "negative" : "neutral"}`}>{row.change}</td>
                    <td className="value">{row.volume}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Sentiment Trend Mini Chart */}
        <Card title="روند احساسات بازار">
          <SentimentChart data={SENTIMENT_DATA.slice(-15)} />
          <div className="sentiment-stats" style={{ marginTop: 8 }}>
            <div className="sentiment-stat">
              <div className="sentiment-stat-label">مثبت</div>
              <div className="sentiment-stat-value positive-value">{SENTIMENT_DATA[SENTIMENT_DATA.length - 1]?.positive}%</div>
            </div>
            <div className="sentiment-stat">
              <div className="sentiment-stat-label">خنثی</div>
              <div className="sentiment-stat-value neutral-value">{SENTIMENT_DATA[SENTIMENT_DATA.length - 1]?.neutral}%</div>
            </div>
            <div className="sentiment-stat">
              <div className="sentiment-stat-label">منفی</div>
              <div className="sentiment-stat-value negative-value">{SENTIMENT_DATA[SENTIMENT_DATA.length - 1]?.negative}%</div>
            </div>
          </div>
        </Card>

        {/* AI Insights */}
        <Card title="تحلیل هوش مصنوعی">
          <div className="ai-insights">
            {MOCK_INSIGHTS.map((insight, i) => (
              <div key={i} className="insight-item">
                <div className={`insight-icon ${insight.type}`}>
                  <span className="material-icons">{insight.icon}</span>
                </div>
                <div className="insight-content">
                  <div className="insight-title">{insight.title}</div>
                  <div className="insight-desc">{insight.description}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ── 🐞 Debug Panel ──────────────────────────────── */}
      <DebugPanel
        logs={logs}
        stats={stats}
        onClear={clearLogs}
        isEnabled={isEnabled}
        onToggle={toggleEnabled}
        onExport={() => {
          const dataStr = JSON.stringify(logs, null, 2);
          const blob = new Blob([dataStr], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `debug-logs-${Date.now()}.json`;
          a.click();
          URL.revokeObjectURL(url);
        }}
      />
    </AppLayout>
  );
}