"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { MarketIndex, generateMockIndices } from "@/lib/types";

function IndexCard({ idx }: { idx: MarketIndex }) {
  return (
    <div className="index-card">
      <div className="index-icon">
        <span className="material-icons text-xl">{idx.icon}</span>
      </div>
      <div className="index-info">
        <span className="index-name">{idx.name}</span>
        <span className="index-value">{idx.value}</span>
        <span className={`index-change ${idx.isUp ? "positive" : "negative"}`}>
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
        // Backend: GET /market/overview returns ApiResponse<{ indices: [...], ... }>
        const res = await apiGet<Record<string, unknown>>("/market/overview");
        // Extract indices from various possible response shapes
        if (res?.indices && Array.isArray(res.indices)) return res.indices as MarketIndex[];
        if (res?.markets && Array.isArray(res.markets)) return res.markets as MarketIndex[];
        if (Array.isArray(res)) return res as MarketIndex[];
        // Try to find any array in the response
        for (const key of ["items", "data", "result"] as const) {
          const val = res?.[key];
          if (val && Array.isArray(val)) return val as MarketIndex[];
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
        <IndexCard key={i} idx={idx} />
      ))}
    </div>
  );
}
