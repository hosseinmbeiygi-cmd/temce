"use client";

import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import { generateMockHeatmap } from "@/lib/types";
import type { HeatmapCell } from "@/lib/types";

function HeatmapCellComponent({ cell }: { cell: HeatmapCell }) {
  const intensity = Math.min(Math.abs(cell.change) / 10, 1);
  const isPositive = cell.change > 0;
  const isNegative = cell.change < 0;

  let bgColor: string;
  if (isPositive) {
    bgColor = `rgba(8, 145, 178, ${0.2 + intensity * 0.6})`;
  } else if (isNegative) {
    bgColor = `rgba(219, 39, 119, ${0.2 + intensity * 0.6})`;
  } else {
    bgColor = `rgba(124, 58, 237, 0.15)`;
  }

  return (
    <div className="heatmap-cell" style={{ backgroundColor: bgColor }}>
      <div className="heatmap-symbol">{cell.symbol}</div>
      <div className="heatmap-change">
        {cell.change > 0 ? "+" : ""}{cell.change.toFixed(2)}%
      </div>
    </div>
  );
}

export default function HeatmapPage() {
  const [view, setView] = useState<"symbols" | "industries">("symbols");
  const cells = generateMockHeatmap();

  // Sort: most positive first
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
        <div className="heatmap">
          {sortedCells.map((cell, i) => (
            <HeatmapCellComponent key={`${cell.symbol}-${i}`} cell={cell} />
          ))}
        </div>
      </Card>
    </AppLayout>
  );
}
