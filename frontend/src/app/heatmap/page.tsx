"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";
import { generateMockHeatmap } from "@/lib/types";
import type { HeatmapCell } from "@/lib/types";
import { useClientData } from "@/hooks/useClientData";
import SSRSafe from "@/components/SSRSafe";

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

      {/* Tooltip on hover */}
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
            {cell.price != null && <TooltipRow label="قیمت" value={cell.price.toLocaleString()} />}
            {cell.freeFloatPct != null && cell.freeFloatPct > 0 && (
              <TooltipRow label="شناوری" value={`${cell.freeFloatPct.toFixed(1)}%`} />
            )}
            {cell.eps != null && cell.eps !== 0 && <TooltipRow label="EPS" value={cell.eps.toLocaleString()} />}
            {cell.peRatio != null && cell.peRatio !== 0 && <TooltipRow label="P/E" value={cell.peRatio.toFixed(1)} />}
            {cell.volume != null && <TooltipRow label="حجم" value={cell.volume.toLocaleString()} />}
            {cell.value != null && <TooltipRow label="ارزش" value={cell.value.toLocaleString()} />}
            {cell.board && <TooltipRow label="تابلو" value={cell.board} />}
          </div>
          {/* Arrow */}
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

export default function HeatmapPage() {
  const [view, setView] = useState<"symbols" | "industries">("symbols");
  const [mockCells] = useClientData(() => generateMockHeatmap(), [] as HeatmapCell[]);

  const { data: apiCells } = useQuery({
    queryKey: ["market-enriched-heatmap"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: HeatmapCell[] }>("/market/enriched-heatmap");
        return extractArray<HeatmapCell>(res);
      } catch {
        return [];
      }
    },
    staleTime: 30000,
  });

  const cells = apiCells && apiCells.length > 0 ? apiCells : mockCells;
  const sortedCells = [...cells].sort((a, b) => b.change - a.change);

  return (
    <AppLayout>
      <Card
        title="نقشه حرارتی بازار"
        actions={
          <>
            <CardAction active={view === "industries"} onClick={() => setView("industries")}>صنایع</CardAction>
            <CardAction active={view === "symbols"} onClick={() => setView("symbols")}>نمادها</CardAction>
          </>
        }
      >
        <SSRSafe className="heatmap-grid" style={{ display: "grid", gap: 4 }}>
          {sortedCells.map((cell, i) => (
            <HeatmapCellComponent key={cell.symbol || i} cell={cell} />
          ))}
        </SSRSafe>
      </Card>
    </AppLayout>
  );
}
