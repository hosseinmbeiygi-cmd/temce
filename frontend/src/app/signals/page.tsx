"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import { apiGet, extractArray } from "@/lib/api";
import { generateMockSignals } from "@/lib/types";
import type { Signal } from "@/lib/types";
import { useClientData } from "@/hooks/useClientData";
import SSRSafe from "@/components/SSRSafe";

export default function SignalsPage() {
  const [filter, setFilter] = useState<"all" | "buy" | "sell" | "neutral">("all");
  const [defaultSignals] = useClientData(() => generateMockSignals(), [] as Signal[]);

  const { data: signals = defaultSignals } = useQuery({
    queryKey: ["signals-full"],
    queryFn: async () => {
      try {
        // Backend: GET /signals returns { success, data: PaginatedResult, summary }
        const res = await apiGet<unknown>("/signals?page=1&page_size=50");
        // apiGet unwraps { success, data: T }, so res = PaginatedResult | { items: [] }
        return extractArray<Signal>(res);
      } catch {
        return generateMockSignals();
      }
    },
    refetchInterval: 30000,
    staleTime: 10000,
  });

  const filtered = filter === "all" ? signals : signals?.filter((s: Signal) => s.signal === filter);

  const getSignalBadge = (signal: string) => {
    const map: Record<string, string> = {
      buy: "bg-accent-emerald/15 text-accent-emerald",
      sell: "bg-accent-rose/15 text-accent-rose",
      neutral: "bg-surface-600/30 text-surface-400",
    };
    return map[signal] || "bg-surface-600/30 text-surface-400";
  };

  const getSignalLabel = (signal: string) => {
    const map: Record<string, string> = { buy: "خرید", sell: "فروش", neutral: "خنثی" };
    return map[signal] || signal;
  };

  return (
    <AppLayout title="سیگنال‌ها" subtitle="سیگنال‌های تولید شده توسط استراتژی‌ها">
      <div className="dashboard-grid" style={{ gridTemplateColumns: "1fr", gridTemplateRows: "1fr" }}>
        <Card
          title="لیست سیگنال‌ها"
          actions={
            <>
              <CardAction active={filter === "all"} onClick={() => setFilter("all")}>همه</CardAction>
              <CardAction active={filter === "buy"} onClick={() => setFilter("buy")}>خرید</CardAction>
              <CardAction active={filter === "sell"} onClick={() => setFilter("sell")}>فروش</CardAction>
              <CardAction active={filter === "neutral"} onClick={() => setFilter("neutral")}>خنثی</CardAction>
            </>
          }
        >
          <SSRSafe style={{ overflowY: "auto", height: "100%" }}>
            {(!Array.isArray(signals) || signals.length === 0) ? (
              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                <span className="material-icons" style={{ fontSize: 48, marginBottom: 10 }}>signal_cellular_alt</span>
                <p>هیچ سیگنالی یافت نشد</p>
              </div>
            ) : (
              <table className="symbols-table">
                <thead>
                  <tr>
                    <th>نماد</th>
                    <th>سیگنال</th>
                    <th>قدرت</th>
                    <th>افق</th>
                    <th>اطمینان</th>
                    <th>استراتژی</th>
                    <th>زمان</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered?.map((s: Signal, i: number) => (
                    <tr key={s.id || i}>
                      <td className="symbol">{s.symbol || s.instrument_id || "—"}</td>
                      <td>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getSignalBadge(s.signal)}`}>
                          {getSignalLabel(s.signal)}
                        </span>
                      </td>
                      <td className="value">{s.strength ? `${(s.strength * 100).toFixed(0)}%` : "—"}</td>
                      <td className="value">{s.horizon || "—"}</td>
                      <td className="value">{s.confidence || "—"}</td>
                      <td style={{ color: "var(--text-secondary)", fontSize: 11 }}>{s.strategy || "—"}</td>
                      <td style={{ color: "var(--text-secondary)", fontSize: 11 }}>{s.created_at || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SSRSafe>
        </Card>
      </div>
    </AppLayout>
  );
}
