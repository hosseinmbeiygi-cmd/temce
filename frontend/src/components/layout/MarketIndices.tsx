"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
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
    queryFn: async () => {
      try {
        // Backend: GET /market/overview returns ApiResponse<{ indices: [...], ... }>
        const res = await apiGet<any>("/market/overview");
        // Extract indices from various possible response shapes
        if (res?.indices) return res.indices;
        if (res?.markets) return res.markets;
        if (Array.isArray(res)) return res;
        // Try to find any array in the response
        for (const key of ["items", "data", "result"]) {
          if (res?.[key] && Array.isArray(res[key])) return res[key];
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
