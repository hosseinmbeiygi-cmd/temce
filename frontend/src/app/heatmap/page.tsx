"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Treemap, ResponsiveContainer, Tooltip } from "recharts";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { getDataAsOf, isDataAsOfFresh } from "@/lib/api-envelope";
import LiveDataBanner from "@/components/dashboard/LiveDataBanner";
import type { HeatmapCell, TreemapData, TreemapSymbol } from "@/lib/types";
import { useEnrichedHeatmap } from "@/hooks/useMarketData";
import SSRSafe from "@/components/SSRSafe";
import TreemapContent from "./TreemapContent";

function HeatmapCellComponent({ cell }: { cell: HeatmapCell }) {
  const intensity = Math.min(Math.abs(cell.change) / 10, 1);
  const isPositive = cell.change > 0;
  const isNegative = cell.change < 0;
  const [hovered, setHovered] = useState(false);

  let bgColor: string;
  if (isPositive) {
    bgColor = `rgba(8, 145, 178, ${0.2 + intensity * 0.6})`;
  } else if (isNegative) {
    bgColor = `rgba(219, 39, 119, ${0.2 + intensity * 0.6})`;
  } else {
    bgColor = `rgba(124, 58, 237, 0.15)`;
  }

  return (
    <div
      className="heatmap-cell"
      style={{ backgroundColor: bgColor, position: "relative", cursor: "pointer" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="heatmap-symbol">{cell.symbol}</div>
      <div className="heatmap-change">
        {cell.change > 0 ? "+" : ""}{cell.change.toFixed(2)}%
      </div>

      {hovered && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)",
          zIndex: 100, pointerEvents: "none", direction: "rtl", textAlign: "right",
        }}>
          <div style={{
            background: "var(--surface-900, #1e1b4b)", border: "1px solid var(--surface-700, #334155)",
            borderRadius: 10, padding: "10px 14px", boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            fontSize: 11, whiteSpace: "nowrap", minWidth: 160,
          }}>
            <div style={{ fontWeight: 700, fontSize: 12, color: "var(--text-primary)", marginBottom: 6 }}>
              {cell.name || cell.symbol}
            </div>
            {cell.sector && <TooltipRow label="صنعت" value={cell.sector} />}
            {cell.state && (
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
                <span style={{ color: "var(--text-secondary)" }}>وضعیت:</span>
                <span style={{
                  fontWeight: 700, fontSize: 10, padding: "0 6px", borderRadius: 3,
                  background: cell.state === "مجاز" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
                  color: cell.state === "مجاز" ? "var(--positive)" : "var(--negative)",
                }}>{cell.state}</span>
              </div>
            )}
            {cell.price != null && <TooltipRow label="قیمت" value={cell.price.toLocaleString("en-US")} />}
            {cell.freeFloatPct != null && cell.freeFloatPct > 0 && (
              <TooltipRow label="شناوری" value={`${cell.freeFloatPct.toFixed(1)}%`} />
            )}
            {cell.eps != null && cell.eps !== 0 && <TooltipRow label="EPS" value={cell.eps.toLocaleString("en-US")} />}
            {cell.peRatio != null && cell.peRatio !== 0 && <TooltipRow label="P/E" value={cell.peRatio.toFixed(1)} />}
            {cell.volume != null && <TooltipRow label="حجم" value={cell.volume.toLocaleString("en-US")} />}
            {cell.value != null && <TooltipRow label="ارزش" value={cell.value.toLocaleString("en-US")} />}
            {cell.board && <TooltipRow label="تابلو" value={cell.board} />}
          </div>
          <div style={{
            position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)",
            width: 0, height: 0, borderLeft: "6px solid transparent", borderRight: "6px solid transparent",
            borderTop: "6px solid var(--surface-700, #334155)",
          }} />
        </div>
      )}
    </div>
  );
}

function TooltipRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}:</span>
      <span style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function TreemapTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: TreemapSymbol & { sector?: string } }> }) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0].payload;
  if (!data || !data.name || !data.size) return null;

  return (
    <div style={{
      background: "var(--surface-900, #1e1b4b)",
      border: "1px solid var(--surface-700, #334155)",
      borderRadius: 10,
      padding: "12px 16px",
      boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
      fontSize: 12,
      direction: "rtl",
      textAlign: "right",
      minWidth: 180,
    }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)", marginBottom: 8 }}>
        {data.name}
      </div>
      {data.sector && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
          <span style={{ color: "var(--text-secondary)" }}>صنعت:</span>
          <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{data.sector}</span>
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
        <span style={{ color: "var(--text-secondary)" }}>قیمت:</span>
        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--text-primary)" }}>
          {data.price?.toLocaleString("en-US") || "—"}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
        <span style={{ color: "var(--text-secondary)" }}>تغییر:</span>
        <span style={{
          fontFamily: "monospace",
          fontWeight: 700,
          color: data.change > 0 ? "var(--positive)" : data.change < 0 ? "var(--negative)" : "var(--text-secondary)",
        }}>
          {data.change > 0 ? "+" : ""}{data.change?.toFixed(2)}%
        </span>
      </div>
      {data.volume != null && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
          <span style={{ color: "var(--text-secondary)" }}>حجم:</span>
          <span style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--text-primary)" }}>
            {data.volume?.toLocaleString("en-US")}
          </span>
        </div>
      )}
      {data.eps != null && data.eps !== 0 && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
          <span style={{ color: "var(--text-secondary)" }}>EPS:</span>
          <span style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--text-primary)" }}>
            {data.eps?.toLocaleString("en-US")}
          </span>
        </div>
      )}
      {data.peRatio != null && data.peRatio !== 0 && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 4 }}>
          <span style={{ color: "var(--text-secondary)" }}>P/E:</span>
          <span style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--text-primary)" }}>
            {data.peRatio?.toFixed(1)}
          </span>
        </div>
      )}
    </div>
  );
}

export default function HeatmapPage() {
  const [view, setView] = useState<"symbols" | "industries">("industries");

  // Shared with the dashboard widgets (same query key/limit), so the page and
  // the widgets cannot disagree about freshness or fetch the same feed twice.
  const heatmap = useEnrichedHeatmap();

  // Fetch treemap data for industries view.
  const { data: treemapFeed, isLoading: loadingTreemap, isError: treemapError } = useQuery({
    queryKey: ["market-treemap"],
    queryFn: async () => {
      const res = await apiGet<{ success?: boolean; data?: TreemapData; data_as_of?: string | null }>(
        "/market/treemap?limit=2000",
      );
      return { data: res?.data ?? { children: [] }, dataAsOf: getDataAsOf(res) };
    },
    staleTime: 30_000,
    refetchInterval: 120_000,
  });

  // No sample data on this page (audit FE-01): an empty grid or a skeleton is
  // shown until the API answers, and a failure is reported as a failure.
  const sortedCells = [...heatmap.data].sort((a, b) => b.change - a.change);

  // Calculate legend stats from treemap data
  const treemapData = treemapFeed?.data ?? { children: [] };
  const treemapAsOf = treemapFeed?.dataAsOf ?? null;
  const allSymbols = treemapData?.children?.flatMap(s => s.children) ?? [];
  const avgChange = allSymbols.length > 0
    ? allSymbols.reduce((s, sym) => s + (sym.change || 0), 0) / allSymbols.length
    : 0;
  const gainersCount = allSymbols.filter(s => s.change > 0).length;
  const losersCount = allSymbols.filter(s => s.change < 0).length;

  const bannerHasData = view === "symbols" ? heatmap.hasData : allSymbols.length > 0;
  const bannerDataAsOf = view === "symbols" ? heatmap.dataAsOf ?? null : treemapAsOf;
  const bannerIsFresh =
    view === "symbols"
      ? heatmap.isFresh
      : bannerDataAsOf != null && isDataAsOfFresh(bannerDataAsOf);
  const bannerIsStale =
    view === "symbols"
      ? heatmap.isStale
      : bannerHasData && bannerDataAsOf != null && !bannerIsFresh;

  return (
    <AppLayout>
      <Card
        title="نقشه بازار"
        subtitle={allSymbols.length + " نماد فعال • بروزرسانی خودکار"}
        actions={
          <>
            <CardAction active={view === "industries"} onClick={() => setView("industries")}>صنایع</CardAction>
            <CardAction active={view === "symbols"} onClick={() => setView("symbols")}>نمادها</CardAction>
          </>
        }
      >
        <LiveDataBanner
          state={{
            isLive: bannerHasData,
            hasData: bannerHasData,
            isFresh: bannerIsFresh,
            isStale: bannerIsStale,
            isError: heatmap.isError || treemapError,
            isLoading: heatmap.isLoading || loadingTreemap,
            dataAsOf: bannerDataAsOf,
          }}
        />
        {/* Color Legend */}
        {view === "industries" && allSymbols.length > 0 && (
          <div className="flex items-center justify-between gap-4 mb-4 px-2">
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ background: "rgb(5, 197, 60)" }} />
                <span className="text-surface-400">صعودی ({gainersCount})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ background: "rgb(60, 60, 80)" }} />
                <span className="text-surface-400">خنثی</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ background: "rgb(235, 20, 30)" }} />
                <span className="text-surface-400">نزولی ({losersCount})</span>
              </div>
            </div>
            <div className="text-xs text-surface-500">
              میانگین تغییرات: <span className={`font-mono font-bold ${avgChange > 0 ? "text-accent-emerald" : avgChange < 0 ? "text-accent-rose" : "text-surface-400"}`}>
                {avgChange > 0 ? "+" : ""}{avgChange.toFixed(2)}%
              </span>
            </div>
          </div>
        )}

        {view === "industries" ? (
          loadingTreemap ? (
            <div className="space-y-3">
              <Skeleton className="h-[800px] w-full rounded-2xl" />
            </div>
          ) : allSymbols.length > 0 ? (
            <SSRSafe style={{ width: "100%", height: 800 }}>
              <ResponsiveContainer width="100%" height="100%">
                <Treemap
                  data={treemapData?.children as unknown as Array<Record<string, unknown>> ?? []}
                  dataKey="size"
                  aspectRatio={16 / 9}
                  stroke="rgba(0,0,0,0.3)"
                  content={<TreemapContent />}
                >
                  <Tooltip content={<TreemapTooltip />} />
                </Treemap>
              </ResponsiveContainer>
            </SSRSafe>
          ) : (
            <div className="text-center py-16 text-surface-500">
              <p className="text-5xl mb-4">🗺️</p>
              <p className="text-lg">داده‌ای برای نمایش نقشه بازار موجود نیست</p>
              <p className="text-sm mt-1">لطفاً اتصال BrsApi را بررسی کنید</p>
            </div>
          )
        ) : heatmap.isLoading && !heatmap.hasData ? (
          <div className="space-y-3">
            <Skeleton className="h-[800px] w-full rounded-2xl" />
          </div>
        ) : heatmap.isError && !heatmap.hasData ? (
          <div role="alert" className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-lg">دریافت نقشهٔ نمادها ناموفق بود</p>
            <p className="text-sm mt-1">اتصال به سرور برقرار نشد؛ تا رسیدن پاسخ معتبر داده‌ای نمایش داده نمی‌شود.</p>
          </div>
        ) : sortedCells.length > 0 ? (
          <SSRSafe className="heatmap-grid" style={{ display: "grid", gap: 4 }}>
            {sortedCells.map((cell, i) => (
              <HeatmapCellComponent key={cell.symbol || i} cell={cell} />
            ))}
          </SSRSafe>
        ) : (
          <div className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">🗺️</p>
            <p className="text-lg">داده‌ای برای نمایش نمادها موجود نیست</p>
            <p className="text-sm mt-1">پس از اولین همگام‌سازی بازار، این نقشه پر می‌شود.</p>
          </div>
        )}
      </Card>
    </AppLayout>
  );
}
