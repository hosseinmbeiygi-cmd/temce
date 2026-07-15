"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { MarketIndex, generateMockIndices } from "@/lib/types";

function IndexCard({ idx }: { idx: MarketIndex }) {
  return (
    <div className="index-card" data-testid="index-card">
      <div className="index-icon">
        <span className="material-icons text-xl">{idx.icon}</span>
      </div>
      <div className="index-info">
        <span className="index-name" data-testid="index-name">{idx.name}</span>
        <span className="index-value" data-testid="index-value">{idx.value}</span>
        <span className={`index-change ${idx.isUp ? "positive" : "negative"}`} data-testid="index-change">
          <span className="material-icons text-xs">{idx.isUp ? "arrow_upward" : "arrow_downward"}</span>
          {Math.abs(idx.changePercent).toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

export default function MarketIndices() {
  const { data: indices } = useQuery({
    queryKey: ["market-indices"],
    queryFn: async (): Promise<MarketIndex[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: Record<string, unknown>[] }>("/market/indices");
        if (res?.success && Array.isArray(res.data)) {
          return res.data.map((idx: Record<string, unknown>) => ({
            id: String(idx.id ?? ""),
            name: String(idx.name || ""),
            value: Number(idx.index_value ?? idx.value ?? 0),
            changePercent: Number(idx.index_change_pct ?? idx.change_pct ?? 0),
            isUp: Number(idx.index_change_pct ?? idx.change_pct ?? 0) >= 0,
            icon: "📈",
          }));
        }
      } catch {
        // Backend unavailable — use mock data
      }
      return generateMockIndices();
    },
    refetchInterval: 30000,
    staleTime: 10000,
  });

  return (
    <div className="market-indices">
      {indices?.map((idx: MarketIndex, i: number) => (
        <IndexCard key={`${i}-${idx.id || idx.name}`} idx={idx} />
      ))}
    </div>
  );
}
