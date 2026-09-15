"use client";

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import DecisionEngineHeader from "@/components/DecisionEngineHeader";
import Skeleton from "@/components/Skeleton";
import DecisionSubmitter from "@/components/DecisionSubmitter";
import MigrationStatusPanel from "@/components/MigrationStatusPanel";
import QueueStatusPanel from "@/components/QueueStatusPanel";
import { apiGet, apiPost } from "@/lib/api";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";
import { toast } from "sonner";

// ── Types ───────────────────────────────────────────────────────────

interface SystemData {
  name: string;
  name_en: string;
  version: string;
  type: string;
  description: string;
  principles: { code: string; name: string; name_en: string; description: string }[];
  objectives: string[];
  data_sources: { code: string; name: string; description: string; service: string }[];
  decision_outputs: { code: string; name: string; color: string; description: string }[];
  non_functional_requirements: string[];
}

interface LayerData {
  order: number;
  name: string;
  title_fa: string;
  description: string;
  color: string;
  responsibilities: string[];
  services: string[];
  api_endpoints: string[];
}

interface ArchitectureResponse {
  system: SystemData;
  layers: LayerData[];
}

interface FeatureBlock {
  code: string;
  name: string;
  name_en: string;
  color: string;
  icon: string;
  feature_count: number;
  features: { id: number; key: string; name: string; description: string; source: string; role: string }[];
}

interface FeaturesResponse {
  meta: { total_features: number; blocks: number };
  blocks: FeatureBlock[];
}

interface ServiceItem {
  name: string;
  category: string;
  title_fa: string;
  description: string;
  protocol: string;
  schedule?: string;
  depends_on?: string[];
  data_dest?: string[];
}

interface ServicesResponse {
  meta: { total_services: number };
  services: ServiceItem[];
}

interface DBGroup {
  group: string;
  tables: { name: string; title_fa: string; key_columns: string; description: string }[];
}

interface DatabaseResponse {
  meta: { total_tables: number };
  tables: DBGroup[];
}

interface APIEndpoint {
  method: string;
  path: string;
  title_fa: string;
  description: string;
  auth?: string;
  request_body?: string;
  response: string;
}

interface APIResponse {
  meta: { total_internal: number; total_external: number };
  internal: APIEndpoint[];
  external: APIEndpoint[];
}

// ── Score Radar Component ──────────────────────────────────────────

function DSSRadarChart({ scores, size = 180 }: { scores: { label: string; value: number; color: string }[]; size?: number }) {
  const data = scores.map((s) => ({
    metric: s.label,
    value: Math.max(0, Math.min(100, s.value)),
    fullMark: 100,
  }));
  if (data.length === 0) return null;
  return (
    <div dir="ltr">
      <ResponsiveContainer width="100%" height={size}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#334155" strokeDasharray="3 3" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 9 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar name="امتیاز" dataKey="value" stroke={scores[0]?.color || "#6366f1"} fill={scores[0]?.color || "#6366f1"} fillOpacity={0.2} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Helper to fetch JSON from /json directory ──────────────────────

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

// ── Main Page Component ────────────────────────────────────────────

export default function DecisionEnginePage() {
  const [activeTab, setActiveTab] = useState<"overview" | "features" | "services" | "database" | "api">("overview");
  const [expandedLayer, setExpandedLayer] = useState<number | null>(1);
  const [expandedBlock, setExpandedBlock] = useState<string | null>("A");
  const [expandedServiceCat, setExpandedServiceCat] = useState<string>("collectors");

  // ── Data fetching ──
  const { data: archData, isLoading: archLoading } = useQuery({
    queryKey: ["dss-architecture"],
    queryFn: () => fetchJson<ArchitectureResponse>("/json/architecture.json"),
    staleTime: Infinity,
  });

  const { data: featuresData, isLoading: featuresLoading } = useQuery({
    queryKey: ["dss-features"],
    queryFn: () => fetchJson<FeaturesResponse>("/json/features.json"),
    staleTime: Infinity,
  });

  const { data: servicesData, isLoading: servicesLoading } = useQuery({
    queryKey: ["dss-services"],
    queryFn: () => fetchJson<ServicesResponse>("/json/services.json"),
    staleTime: Infinity,
  });

  const { data: dbData, isLoading: dbLoading } = useQuery({
    queryKey: ["dss-database"],
    queryFn: () => fetchJson<DatabaseResponse>("/json/database.json"),
    staleTime: Infinity,
  });

  const { data: apiData, isLoading: apiLoading } = useQuery({
    queryKey: ["dss-api"],
    queryFn: () => fetchJson<APIResponse>("/json/api.json"),
    staleTime: Infinity,
  });

  const hasError = (!archData && !archLoading) || (!featuresData && !featuresLoading) || (!servicesData && !servicesLoading) || (!dbData && !dbLoading) || (!apiData && !apiLoading);
  const isLoading = archLoading || featuresLoading || servicesLoading || dbLoading || apiLoading;

  const system = archData?.system;
  const layers = archData?.layers || [];

  const subScores = [
    { label: "بنیادی (S_F)", value: 82, color: "#3b82f6" },
    { label: "ارزش (S_V)", value: 65, color: "#f59e0b" },
    { label: "تکنیکال (S_T)", value: 74, color: "#06b6d4" },
    { label: "نقدشوندگی (S_L)", value: 70, color: "#10b981" },
    { label: "جریان پول (S_O)", value: 55, color: "#a855f7" },
    { label: "میکرو (S_M)", value: 60, color: "#ef4444" },
    { label: "کلان (S_K)", value: 45, color: "#f97316" },
    { label: "رویدادی (S_E)", value: 50, color: "#6366f1" },
  ];

  // ── Live decisions from API ──
  interface LiveDecision {
    symbol: string;
    final_score: number;
    decision: string;
    confidence: number;
    run_id?: string;
  }

  const { data: liveDecisions, isLoading: decisionsLoading } = useQuery({
    queryKey: ["dss-decisions"],
    queryFn: async () => {
      try {
        const res = await apiGet<{
          success: boolean;
          data: {
            items: {
              symbol: string;
              final_score: number;
              decision: string;
              confidence: number;
              details?: { reasons?: string[] } | null;
              base_score?: number;
              score_fundamental?: number;
              score_technical?: number;
              score_liquidity?: number;
              score_orderflow?: number;
            }[];
            total: number;
          };
        }>("/decision-engine/decisions/buy-candidates?limit=10");
        if (res?.success && res?.data?.items) {
          return res.data.items;
        }
      } catch {
        // Fall back to JSON file
      }
      try {
        const res = await fetch("/json/decisions.json");
        if (res.ok) {
          const json = await res.json();
          return json?.items || [];
        }
      } catch {
        // ignore
      }
      return null;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  // ── Watchlist mutation ──
  const queryClient = useQueryClient();
  const [addingToWatchlist, setAddingToWatchlist] = useState<string | null>(null);

  const addToWatchlist = useCallback(async (symbol: string) => {
    setAddingToWatchlist(symbol);
    try {
      await apiPost("/watchlist", { symbol });
      toast.success(`نماد ${symbol} به لیست پیگیری اضافه شد`);
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    } catch {
      toast.error(`خطا در افزودن ${symbol} به لیست پیگیری`);
    }
    setAddingToWatchlist(null);
  }, [queryClient]);

  // ── Decision color helper ──
  function decisionColor(d: string): string {
    switch (d) {
      case "BUY": return "#10b981";
      case "WATCHLIST": return "#06b6d4";
      case "HOLD": return "#f59e0b";
      case "REDUCE": return "#f97316";
      case "REJECT": return "#ef4444";
      default: return "#6366f1";
    }
  }

  function decisionLabel(d: string): string {
    switch (d) {
      case "BUY": return "خرید";
      case "WATCHLIST": return "نظارت";
      case "HOLD": return "نگهداری";
      case "REDUCE": return "کاهش";
      case "REJECT": return "رد";
      default: return "خنثی";
    }
  }

  const tabs = [
    { key: "overview" as const, label: "نمای کلی", icon: "dashboard" },
    { key: "features" as const, label: "۱۱۰ ویژگی", icon: "list_alt" },
    { key: "services" as const, label: "سرویس‌ها", icon: "dns" },
    { key: "database" as const, label: "دیتابیس", icon: "storage" },
    { key: "api" as const, label: "API", icon: "api" },
  ];

  if (hasError) {
    return (
      <AppLayout title="موتور تصمیم‌یار" subtitle="سامانه تصمیم‌یار بورس تهران">
        <div className="glass-card p-6 text-center">
          <span className="material-icons text-3xl text-accent-rose mb-2">cloud_off</span>
          <p className="text-sm text-surface-400">خطا در دریافت داده‌های معماری</p>
          <p className="text-xs text-surface-500 mt-1">فایل‌های JSON در دسترس نیستند. لطفاً مطمئن شوید فایل‌ها در مسیر public/json قرار دارند.</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-3 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-xs transition-all"
          >
            تلاش مجدد
          </button>
        </div>
      </AppLayout>
    );
  }

  if (isLoading) {
    return (
      <AppLayout title="موتور تصمیم‌یار" subtitle="سامانه تصمیم‌یار بورس تهران">
        <div className="space-y-4">
          <Skeleton className="h-12 w-80 rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </AppLayout>
    );
  }

  function renderScoreBar(label: string, value: number, color: string) {
    const pct = Math.max(0, Math.min(100, value));
    return (
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium text-surface-400 w-28 text-right shrink-0">{label}</span>
        <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
        </div>
        <span className="text-[11px] font-bold font-mono text-surface-200 w-8 text-left">{pct}</span>
      </div>
    );
  }

  return (
    <AppLayout
      title="موتور تصمیم‌یار"
      subtitle="سامانه تصمیم‌یار بورس تهران — Enterprise Edition v1.0"
      header={
        <DecisionEngineHeader
          title={system?.name || "سامانه تصمیم‌یار بورس تهران"}
          description={system?.description}
          version={system?.version}
          type={system?.type}
          principles={system?.principles}
          dataSources={system?.data_sources}
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(key) => setActiveTab(key as typeof activeTab)}
        />
      }
    >

      {/* ═══════════════ OVERVIEW TAB ═══════════════ */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          {/* 12 Layers Timeline */}
          <div className="glass-card p-4">
            <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
              <span className="material-icons text-primary-400 text-sm">layers</span>
              معماری ۱۲ لایه
            </h2>
            <div className="space-y-2">
              {layers.map((layer, i) => (
                <div key={layer.order} className="rounded-xl border border-surface-700/30 overflow-hidden transition-all">
                  <button
                    onClick={() => setExpandedLayer(expandedLayer === layer.order ? null : layer.order)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 bg-surface-800/30 hover:bg-surface-800/50 transition-colors text-right"
                  >
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black text-white shrink-0" style={{ backgroundColor: layer.color }}>
                      {layer.order}
                    </div>
                    <span className="flex-1 text-xs font-bold text-surface-200">{layer.title_fa}</span>
                    <span className="text-[9px] text-surface-500 font-mono">{layer.name}</span>
                    <span className="material-icons text-sm text-surface-500 transition-transform" style={{ transform: expandedLayer === layer.order ? "rotate(180deg)" : "rotate(0deg)" }}>
                      expand_more
                    </span>
                  </button>
                  {expandedLayer === layer.order && (
                    <div className="px-4 pb-3 pt-1 border-t border-surface-700/20">
                      <p className="text-[10px] text-surface-400 leading-relaxed mb-2">{layer.description}</p>
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {layer.responsibilities.map((r, j) => (
                          <span key={j} className="text-[9px] px-2 py-0.5 bg-surface-800/50 rounded-full text-surface-500">
                            {r}
                          </span>
                        ))}
                      </div>
                      {layer.services.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {layer.services.map((s) => (
                            <span key={s} className="text-[8px] px-1.5 py-0.5 bg-primary-600/10 border border-primary-600/20 rounded text-primary-300 font-mono">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Sub-Scores Radar + Bars */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
            <div className="glass-card p-4">
              <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
                <span className="material-icons text-accent-violet text-sm">radar</span>
                رادار ۸ سوبرسکور
              </h2>
              <DSSRadarChart scores={subScores.map(s => ({ ...s, value: s.value }))} size={220} />
              <div className="flex flex-wrap justify-center gap-2 mt-2">
                {subScores.map((s) => (
                  <span key={s.label} className="text-[9px] px-2 py-0.5 rounded-full border" style={{ borderColor: s.color + "30", color: s.color }}>
                    {s.label}: {s.value}
                  </span>
                ))}
              </div>
            </div>

            <div className="glass-card p-4">
              <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
                <span className="material-icons text-accent-emerald text-sm">speed</span>
                نمرات و زیرامتیازها
              </h2>
              <div className="space-y-2.5">
                {subScores.map((s) => renderScoreBar(s.label, s.value, s.color))}
              </div>
              <div className="mt-3 pt-3 border-t border-surface-800/50 flex items-center justify-between">
                <span className="text-xs font-bold text-surface-300">BaseScore وزنی</span>
                <span className="text-lg font-black text-primary-300">۶۴</span>
              </div>
            </div>
          </div>

          {/* ── Live Decisions + Watchlist ── */}
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-surface-200 flex items-center gap-2">
                <span className="material-icons text-sm">fact_check</span>
                تصمیمات خرید (لایو)
              </h2>
              <div className="flex items-center gap-2">
                {decisionsLoading && (
                  <div className="flex items-center gap-1 text-[9px] text-surface-500">
                    <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />
                    در حال بارگذاری...
                  </div>
                )}
                {liveDecisions && Array.isArray(liveDecisions) && (
                  <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-lg">
                    {liveDecisions.length} کاندیدا
                  </span>
                )}
              </div>
            </div>

            {liveDecisions && Array.isArray(liveDecisions) && liveDecisions.length > 0 ? (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-surface-700/50">
                        <th className="text-right px-2 py-2 text-[10px] font-medium text-surface-500">نماد</th>
                        <th className="text-center px-2 py-2 text-[10px] font-medium text-surface-500">امتیاز</th>
                        <th className="text-center px-2 py-2 text-[10px] font-medium text-surface-500">تصمیم</th>
                        <th className="text-center px-2 py-2 text-[10px] font-medium text-surface-500">اطمینان</th>
                        <th className="text-right px-2 py-2 text-[10px] font-medium text-surface-500">لیست پیگیری</th>
                      </tr>
                    </thead>
                    <tbody>
                      {liveDecisions.map((ex: LiveDecision) => (
                        <tr key={ex.symbol} className="border-b border-surface-800/30 hover:bg-surface-800/20 transition-colors">
                          <td className="px-2 py-2.5">
                            <span className="font-bold text-primary-300">{ex.symbol}</span>
                          </td>
                          <td className="px-2 py-2.5 text-center">
                            <span className="font-mono font-bold text-surface-200">{ex.final_score?.toFixed(0) || "—"}</span>
                          </td>
                          <td className="px-2 py-2.5 text-center">
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: decisionColor(ex.decision) }}>
                              {decisionLabel(ex.decision)}
                            </span>
                          </td>
                          <td className="px-2 py-2.5 text-center">
                            <div className="flex items-center justify-center gap-1">
                              <div className="w-12 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                                <div className="h-full rounded-full" style={{ width: `${(ex.confidence || 0) * 100}%`, backgroundColor: decisionColor(ex.decision) }} />
                              </div>
                              <span className="font-mono text-[10px] text-surface-400">{((ex.confidence || 0) * 100).toFixed(0)}%</span>
                            </div>
                          </td>
                          <td className="px-2 py-2.5 text-center">
                            <button
                              onClick={() => addToWatchlist(ex.symbol)}
                              disabled={addingToWatchlist === ex.symbol}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[9px] font-bold transition-all bg-accent-emerald/10 text-accent-emerald hover:bg-accent-emerald/20 disabled:opacity-40"
                            >
                              <span className="material-icons text-xs">
                                {addingToWatchlist === ex.symbol ? "hourglass_top" : "star_border"}
                              </span>
                              افزودن
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="md:hidden space-y-2">
                  {liveDecisions.map((ex: LiveDecision) => (
                    <div key={ex.symbol} className="rounded-xl p-3 border border-surface-700/30 bg-surface-800/20">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold text-primary-300">{ex.symbol}</span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: decisionColor(ex.decision) }}>
                          {decisionLabel(ex.decision)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-surface-500">امتیاز نهایی</span>
                        <span className="font-mono font-bold text-surface-200">{ex.final_score?.toFixed(0) || "—"}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] mt-1">
                        <span className="text-surface-500">اطمینان</span>
                        <div className="flex items-center gap-1">
                          <div className="w-16 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${(ex.confidence || 0) * 100}%`, backgroundColor: decisionColor(ex.decision) }} />
                          </div>
                          <span className="font-mono text-surface-400">{((ex.confidence || 0) * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <button
                        onClick={() => addToWatchlist(ex.symbol)}
                        disabled={addingToWatchlist === ex.symbol}
                        className="w-full mt-2 flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-[10px] font-bold transition-all bg-accent-emerald/10 text-accent-emerald hover:bg-accent-emerald/20 disabled:opacity-40"
                      >
                        <span className="material-icons text-sm">
                          {addingToWatchlist === ex.symbol ? "hourglass_top" : "star_border"}
                        </span>
                        افزودن به لیست پیگیری
                      </button>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="py-6 text-center">
                <span className="material-icons text-2xl text-surface-600 mb-2">inbox</span>
                <p className="text-[11px] text-surface-500">
                  {decisionsLoading ? "در حال دریافت آخرین تصمیمات..." : "هیچ تصمیم فعالی یافت نشد. پس از اجرای موتور تصمیم، نتایج در این بخش نمایش داده می‌شوند."}
                </p>
              </div>
            )}
          </div>

          {/* ── Decision Submitter ── */}
          <DecisionSubmitter />

          {/* ── Queue Analysis Panel ── */}
          <QueueStatusPanel />

          {/* Decision Pipeline */}
          <div className="glass-card p-4">
            <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
              <span className="material-icons text-sm">account_tree</span>
              خط لوله ۳ گامه تصمیم
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {[
                { step: "گام اول", name: "غربالگری سریع", desc: "همه نمادها با داده‌های تابلو، کندل، کدال، جریان پول و کلان", output: "BaseScore", color: "#06b6d4" },
                { step: "گام دوم", name: "تحلیل عمیق", desc: "فقط کاندیداهای منتخب با تحلیل ریزمعاملات و ریزساختار", output: "S_M + MicroAdjustment", color: "#f59e0b" },
                { step: "گام سوم", name: "تصمیم نهایی", desc: "ترکیب BaseScore + MicroAdjustment + Penalty با Rulebook", output: "FinalScore + FinalDecision", color: "#10b981" },
              ].map((g, i) => (
                <div key={i} className="rounded-xl p-4 border" style={{ borderColor: g.color + "20", backgroundColor: g.color + "08" }}>
                  <div className="text-[9px] font-bold mb-1" style={{ color: g.color }}>{g.step}</div>
                  <div className="text-xs font-bold text-surface-200 mb-1">{g.name}</div>
                  <p className="text-[10px] text-surface-500 leading-relaxed mb-2">{g.desc}</p>
                  <div className="text-[9px] font-mono px-2 py-0.5 rounded bg-surface-800/50 inline-block text-surface-400">{g.output}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════ FEATURES TAB ═══════════════ */}
      {activeTab === "features" && (
        <div className="glass-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-surface-200 flex items-center gap-2">
              <span className="material-icons text-sm">list_alt</span>
              ۱۱۰ ویژگی در {featuresData?.meta.blocks} بلوک
            </h2>
            <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-1 rounded-lg">{featuresData?.meta.total_features} ویژگی</span>
          </div>

          {/* Block tabs */}
          <div className="flex flex-wrap gap-1 mb-3">
            {featuresData?.blocks.map((block) => (
              <button
                key={block.code}
                onClick={() => setExpandedBlock(expandedBlock === block.code ? null : block.code)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                  expandedBlock === block.code ? "text-white" : "text-surface-400 bg-surface-800/50 hover:bg-surface-800"
                }`}
                style={expandedBlock === block.code ? { backgroundColor: block.color } : {}}
              >
                <span className="material-icons text-xs">{block.icon}</span>
                بلوک {block.code}: {block.name}
                <span className="text-[8px] opacity-70">({block.feature_count})</span>
              </button>
            ))}
          </div>

          {/* Feature tables */}
          {featuresData?.blocks.filter((b) => expandedBlock === b.code).map((block) => (
            <div key={block.code} className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="border-b border-surface-700/50">
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500 w-8">#</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">ویژگی</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500 w-[30%]">توضیح</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">منبع</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">نقش در سیستم</th>
                  </tr>
                </thead>
                <tbody>
                  {block.features.map((f) => (
                    <tr key={f.id} className="border-b border-surface-800/20 hover:bg-surface-800/20 transition-colors">
                      <td className="px-2 py-2 font-mono text-surface-500">{f.id}</td>
                      <td className="px-2 py-2">
                        <span className="font-bold text-surface-200">{f.name}</span>
                        <span className="text-[8px] text-surface-500 mr-1 font-mono">({f.key})</span>
                      </td>
                      <td className="px-2 py-2 text-surface-400">{f.description}</td>
                      <td className="px-2 py-2">
                        <span className="text-[8px] px-1.5 py-0.5 bg-surface-800 rounded text-surface-500">{f.source}</span>
                      </td>
                      <td className="px-2 py-2 text-surface-500">{f.role}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {!featuresData?.blocks.find((b) => expandedBlock === b.code) && (
            <div className="py-6 text-center text-[11px] text-surface-500">
              روی یک بلوک کلیک کنید تا ویژگی‌های آن نمایش داده شود
            </div>
          )}
        </div>
      )}

      {/* ═══════════════ SERVICES TAB ═══════════════ */}
      {activeTab === "services" && (
        <div className="space-y-4">
          {/* Category tabs */}
          <div className="flex gap-2">
            {[
              { key: "collectors", label: "دریافت داده", count: 5, icon: "download" },
              { key: "processors", label: "پردازشی", count: 11, icon: "memory" },
              { key: "management", label: "مدیریتی", count: 6, icon: "admin_panel_settings" },
            ].map((cat) => (
              <button
                key={cat.key}
                onClick={() => setExpandedServiceCat(cat.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                  expandedServiceCat === cat.key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                }`}
              >
                <span className="material-icons text-xs">{cat.icon}</span>
                {cat.label}
                <span className="text-[8px] opacity-70">({cat.count})</span>
              </button>
            ))}
          </div>

          <div className="glass-card p-4">
            <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
              <span className="material-icons text-sm">dns</span>
              سرویس‌های {expandedServiceCat === "collectors" ? "دریافت داده" : expandedServiceCat === "processors" ? "پردازشی" : "مدیریتی"}
              <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full font-normal">
                {servicesData?.services.filter((s) => s.category === expandedServiceCat).length} سرویس
              </span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {servicesData?.services
                .filter((s) => s.category === expandedServiceCat)
                .map((svc) => (
                  <div key={svc.name} className="rounded-xl p-3 border border-surface-700/30 bg-surface-800/20 hover:bg-surface-800/40 transition-all">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[11px] font-bold text-primary-300 font-mono">{svc.name}</span>
                      <span className="text-[8px] px-1.5 py-0.5 rounded bg-surface-800 text-surface-500">{svc.protocol}</span>
                    </div>
                    <p className="text-[10px] text-surface-400 mb-2">{svc.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {svc.schedule && (
                        <span className="text-[8px] px-1.5 py-0.5 bg-accent-amber/10 border border-accent-amber/20 rounded text-accent-300">{svc.schedule}</span>
                      )}
                      {svc.depends_on?.map((dep) => (
                        <span key={dep} className="text-[8px] px-1.5 py-0.5 bg-accent-rose/10 border border-accent-rose/20 rounded text-accent-300">
                          ← {dep}
                        </span>
                      ))}
                      {svc.data_dest?.map((dest) => (
                        <span key={dest} className="text-[8px] px-1.5 py-0.5 bg-accent-cyan/10 border border-accent-cyan/20 rounded text-accent-300">
                          {dest}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Service Pipeline */}
          <div className="glass-card p-4">
            <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
              <span className="material-icons text-sm">linear_scale</span>
              خط لوله سرویس‌های پردازشی
            </h2>
            <div className="flex flex-wrap items-center gap-1.5">
              {servicesData?.services
                .filter((s) => s.category === "processors")
                .map((svc, i) => (
                  <div key={svc.name} className="flex items-center gap-1.5">
                    <span className="text-[9px] px-2 py-1 rounded-lg bg-primary-600/10 border border-primary-600/20 text-primary-300 font-mono whitespace-nowrap">
                      {svc.name.split("-").slice(0, 2).join("-")}
                    </span>
                    {i < 10 && <span className="text-[8px] text-surface-600">→</span>}
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════ DATABASE TAB ═══════════════ */}
      {activeTab === "database" && (
        <div className="space-y-4">
          {/* Migration & Table Status */}
          <MigrationStatusPanel />

          {dbData?.tables.map((group) => (
            <div key={group.group} className="glass-card p-4">
              <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
                <span className="material-icons text-sm">storage</span>
                {group.group === "reference" && "جداول مرجع"}
                {group.group === "raw" && "جداول خام"}
                {group.group === "quality" && "جداول کیفیت داده"}
                {group.group === "feature" && "جداول ویژگی‌ها"}
                {group.group === "score" && "جداول امتیاز"}
                {group.group === "decision" && "جداول تصمیم و ممیزی"}
                {group.group === "ops" && "جداول عملیاتی"}
                <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full font-normal">{group.tables.length} جدول</span>
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="border-b border-surface-700/50">
                      <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">نام جدول</th>
                      <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">توضیح</th>
                      <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">ستون‌های کلیدی</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.tables.map((tbl) => (
                      <tr key={tbl.name} className="border-b border-surface-800/20 hover:bg-surface-800/20 transition-colors">
                        <td className="px-2 py-2 font-mono font-bold text-primary-300">{tbl.name}</td>
                        <td className="px-2 py-2 text-surface-400">{tbl.description}</td>
                        <td className="px-2 py-2">
                          <span className="text-[8px] text-surface-500 font-mono">{tbl.key_columns}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ═══════════════ API TAB ═══════════════ */}
      {activeTab === "api" && (
        <div className="space-y-4">
          {/* Internal APIs */}
          <div className="glass-card p-4">
            <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
              <span className="material-icons text-sm">settings_ethernet</span>
              APIهای داخلی (پردازشی)
              <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full font-normal">{apiData?.internal.length} اندپوینت</span>
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="border-b border-surface-700/50">
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">متد</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">مسیر</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">توضیح</th>
                  </tr>
                </thead>
                <tbody>
                  {apiData?.internal.map((ep) => (
                    <tr key={ep.path} className="border-b border-surface-800/20 hover:bg-surface-800/20 transition-colors">
                      <td className="px-2 py-2">
                        <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-accent-emerald/10 text-accent-emerald">{ep.method}</span>
                      </td>
                      <td className="px-2 py-2 font-mono text-primary-300">{ep.path}</td>
                      <td className="px-2 py-2 text-surface-400">{ep.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* External APIs */}
          <div className="glass-card p-4">
            <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
              <span className="material-icons text-sm">link</span>
              APIهای بیرونی (مصرف‌کننده)
              <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full font-normal">{apiData?.external.length} اندپوینت</span>
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="border-b border-surface-700/50">
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">متد</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">مسیر</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">توضیح</th>
                    <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">احراز</th>
                  </tr>
                </thead>
                <tbody>
                  {apiData?.external.map((ep) => (
                    <tr key={ep.path} className="border-b border-surface-800/20 hover:bg-surface-800/20 transition-colors">
                      <td className="px-2 py-2">
                        <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-accent-emerald/10 text-accent-emerald">{ep.method}</span>
                      </td>
                      <td className="px-2 py-2 font-mono text-primary-300">{ep.path}</td>
                      <td className="px-2 py-2 text-surface-400">{ep.description}</td>
                      <td className="px-2 py-2 text-surface-500">{ep.auth}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
