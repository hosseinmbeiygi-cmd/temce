"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────

interface FakeQueueItem {
  symbol: string;
  name: string;
  fake_buy_queue: boolean;
  fake_sell_queue: boolean;
  confidence: number;
  reason: string;
}

interface AccumulationItem {
  symbol: string;
  name: string;
  score: number;
  volume_ratio: number;
  price_change_pct: number;
  net_real_flow: number;
  reason: string;
}

interface ManipulationItem {
  symbol: string;
  name: string;
  pattern: string;
  confidence: number;
  severity: string;
  reason: string;
  recommendation: string;
}

interface FearGreedData {
  overall_score: number;
  label: string;
  components: Record<string, number>;
  date: string;
}

interface MarketHealthData {
  overall_score: number;
  label: string;
  components: Record<string, number>;
  recommendations: string[];
  date: string;
}

interface BlockTradeItem {
  symbol: string;
  name: string;
  trade_time: string;
  price: number;
  volume: number;
  value: number;
  direction: string;
  z_score: number;
}

// ── Tab Types ──────────────────────────────────────────────────────────

type TabId = "fear-greed" | "health" | "fake-queues" | "accumulation" | "manipulation" | "block-trades";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "fear-greed", label: "ترس و طمع", icon: "😱" },
  { id: "health", label: "سلامت بازار", icon: "💓" },
  { id: "fake-queues", label: "صف کاذب", icon: "🎭" },
  { id: "accumulation", label: "انباشت پنهان", icon: "🏦" },
  { id: "manipulation", label: "دستکاری", icon: "⚠️" },
  { id: "block-trades", label: "معاملات بلوکی", icon: "📦" },
];

// ── Score Badge ────────────────────────────────────────────────────────

function ScoreBadge({ score, max = 100 }: { score: number; max?: number }) {
  const pct = (score / max) * 100;
  let color = "bg-gray-500";
  if (pct >= 70) color = "bg-green-500";
  else if (pct >= 50) color = "bg-yellow-500";
  else if (pct >= 30) color = "bg-orange-500";
  else color = "bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-mono">{score.toFixed(1)}</span>
    </div>
  );
}

// ── Fear & Greed Tab ──────────────────────────────────────────────────

function FearGreedTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["fear-greed"],
    queryFn: () => apiGet<FearGreedData>("/market-insights/fear-greed"),
    refetchInterval: 300000,
  });

  if (isLoading) return <Skeleton className="h-64" />;
  const d = data as unknown as FearGreedData;
  if (!d) return <div className="text-gray-400">داده‌ای موجود نیست</div>;

  const scoreColor = d.overall_score >= 70 ? "text-green-400" : d.overall_score >= 50 ? "text-yellow-400" : d.overall_score >= 30 ? "text-orange-400" : "text-red-400";

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className={`text-6xl font-bold ${scoreColor}`}>{d.overall_score}</div>
        <div className="text-xl mt-2">{d.label}</div>
        <div className="text-sm text-gray-400">{d.date}</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {d.components && Object.entries(d.components).map(([key, val]) => (
          <div key={key} className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">
              {key === "real_legal_ratio" ? "نسبت خرید حقیقی/حقوقی" :
               key === "activity_level" ? "سطح فعالیت بازار" :
               key === "trend_extension" ? "فاصله از میانگین ۲۰۰ روزه" :
               key === "volatility" ? "نوسان‌پذیری" :
               "احساسات اخبار"}
            </div>
            <ScoreBadge score={val} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Market Health Tab ──────────────────────────────────────────────────

function MarketHealthTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["market-health"],
    queryFn: () => apiGet<MarketHealthData>("/market-insights/market-health"),
    refetchInterval: 300000,
  });

  if (isLoading) return <Skeleton className="h-64" />;
  const d = data as unknown as MarketHealthData;
  if (!d) return <div className="text-gray-400">داده‌ای موجود نیست</div>;

  const scoreColor = d.overall_score >= 70 ? "text-green-400" : d.overall_score >= 50 ? "text-yellow-400" : d.overall_score >= 30 ? "text-orange-400" : "text-red-400";

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className={`text-6xl font-bold ${scoreColor}`}>{d.overall_score}</div>
        <div className="text-xl mt-2">{d.label}</div>
      </div>

      {d.recommendations && (
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="text-sm font-medium mb-2">پیشنهادات:</div>
          <ul className="space-y-1">
            {d.recommendations.map((r, i) => (
              <li key={i} className="text-sm text-gray-300">• {r}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {d.components && Object.entries(d.components).map(([key, val]) => (
          <div key={key} className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">
              {key === "real_legal_flow" ? "جریان پول حقیقی/حقوقی" :
               key === "price_dispersion" ? "پراکندگی قیمت" :
               key === "block_trade_ratio" ? "نسبت معاملات بلوکی" :
               "ثبات VWAP"}
            </div>
            <ScoreBadge score={val} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Fake Queues Tab ────────────────────────────────────────────────────

function FakeQueuesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["fake-queues"],
    queryFn: () => apiGet<{ items: FakeQueueItem[]; total: number }>("/market-insights/fake-queues?limit=50"),
    refetchInterval: 60000,
  });

  if (isLoading) return <Skeleton className="h-64" />;
  const d = data as unknown as { items: FakeQueueItem[]; total: number };
  if (!d?.items?.length) return <div className="text-gray-400">صف کاذبی شناسایی نشد</div>;

  return (
    <div className="space-y-2">
      {d.items.map((item) => (
        <div key={item.symbol} className="bg-gray-800/50 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="font-medium">{item.symbol}</span>
            <span className="text-gray-400 text-sm mr-2">{item.name}</span>
          </div>
          <div className="flex items-center gap-3">
            {item.fake_buy_queue && <span className="text-red-400 text-sm">🎭 صف خرید کاذب</span>}
            {item.fake_sell_queue && <span className="text-orange-400 text-sm">🎭 صف فروش کاذب</span>}
            <span className="text-sm text-gray-400">{(item.confidence * 100).toFixed(0)}٪ اطمینان</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Accumulation Tab ───────────────────────────────────────────────────

function AccumulationTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["accumulation"],
    queryFn: () => apiGet<{ items: AccumulationItem[]; total: number }>("/market-insights/accumulation?limit=50"),
    refetchInterval: 60000,
  });

  if (isLoading) return <Skeleton className="h-64" />;
  const d = data as unknown as { items: AccumulationItem[]; total: number };
  if (!d?.items?.length) return <div className="text-gray-400">انباشت پنهانی شناسایی نشد</div>;

  return (
    <div className="space-y-2">
      {d.items.map((item) => (
        <div key={item.symbol} className="bg-gray-800/50 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="font-medium">{item.symbol}</span>
            <span className="text-gray-400 text-sm mr-2">{item.name}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm">امتیاز: {item.score.toFixed(0)}</span>
            <span className="text-sm text-blue-400">حجم: {item.volume_ratio.toFixed(1)}x</span>
            <span className="text-sm text-gray-400">{item.reason}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Manipulation Tab ───────────────────────────────────────────────────

function ManipulationTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["manipulation"],
    queryFn: () => apiGet<{ items: ManipulationItem[]; total: number }>("/market-insights/manipulation?limit=50"),
    refetchInterval: 60000,
  });

  if (isLoading) return <Skeleton className="h-64" />;
  const d = data as unknown as { items: ManipulationItem[]; total: number };
  if (!d?.items?.length) return <div className="text-gray-400">دستکاری شناسایی نشد</div>;

  return (
    <div className="space-y-2">
      {d.items.map((item, idx) => (
        <div key={idx} className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-medium">{item.symbol}</span>
              <span className="text-gray-400 text-sm mr-2">{item.name}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm px-2 py-0.5 rounded ${
                item.severity === "high" ? "bg-red-500/20 text-red-400" :
                item.severity === "medium" ? "bg-orange-500/20 text-orange-400" :
                "bg-yellow-500/20 text-yellow-400"
              }`}>
                {item.pattern === "pump_and_dump" ? "پامپ و دامپ" :
                 item.pattern === "range_trap" ? "دامنه" : item.pattern}
              </span>
              <span className="text-sm text-gray-400">{(item.confidence * 100).toFixed(0)}٪</span>
            </div>
          </div>
          <div className="text-sm text-gray-400 mt-1">{item.reason}</div>
          <div className="text-sm text-orange-300 mt-1">پیشنهاد: {item.recommendation}</div>
        </div>
      ))}
    </div>
  );
}

// ── Block Trades Tab ───────────────────────────────────────────────────

function BlockTradesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["block-trades"],
    queryFn: () => apiGet<{ items: BlockTradeItem[]; total: number }>("/market-insights/block-trades?limit=30"),
    refetchInterval: 60000,
  });

  if (isLoading) return <Skeleton className="h-64" />;
  const d = data as unknown as { items: BlockTradeItem[]; total: number };
  if (!d?.items?.length) return <div className="text-gray-400">معامله بلوکی شناسایی نشد</div>;

  return (
    <div className="space-y-2">
      {d.items.map((item, idx) => (
        <div key={idx} className="bg-gray-800/50 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="font-medium">{item.symbol}</span>
            <span className="text-gray-400 text-sm mr-2">{item.name}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-sm px-2 py-0.5 rounded ${
              item.direction === "accumulation" ? "bg-green-500/20 text-green-400" :
              item.direction === "distribution" ? "bg-red-500/20 text-red-400" :
              "bg-gray-500/20 text-gray-400"
            }`}>
              {item.direction === "accumulation" ? "انباشت" :
               item.direction === "distribution" ? "توزیع" : "خنثی"}
            </span>
            <span className="text-sm text-gray-400">z={item.z_score.toFixed(1)}</span>
            <span className="text-sm">{(item.value / 1e9).toFixed(1)} میلیارد</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────

export default function MarketInsightsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("fear-greed");

  return (
    <AppLayout>
      <div className="p-4 space-y-4">
        <h1 className="text-2xl font-bold">بینش بازار</h1>

        {/* Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="bg-gray-900/50 rounded-xl p-6">
          {activeTab === "fear-greed" && <FearGreedTab />}
          {activeTab === "health" && <MarketHealthTab />}
          {activeTab === "fake-queues" && <FakeQueuesTab />}
          {activeTab === "accumulation" && <AccumulationTab />}
          {activeTab === "manipulation" && <ManipulationTab />}
          {activeTab === "block-trades" && <BlockTradesTab />}
        </div>
      </div>
    </AppLayout>
  );
}
