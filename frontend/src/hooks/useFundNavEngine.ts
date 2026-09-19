"use client";

/**
 * 🧮 useFundNavEngine — React Query hooks برای موتور NAV مستقل و تطبیق.
 *
 * همه مسیرها زیر `/funds/v2/nav` هستند و envelope استاندارد
 * `{ success, data, freshness, fetched_from }` برمی‌گردانند.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type {
  FundNavBreak,
  FundNavDashboard,
  FundNavReconciliation,
  FundNavRun,
} from "@/lib/fund-nav";

interface Envelope<T> {
  success: boolean;
  data: T;
  freshness?: string;
  fetched_from?: string;
}

const NAV_BASE = "/funds/v2/nav";

function navUrl(symbol: string, suffix: string): string {
  return `${NAV_BASE}/${encodeURIComponent(symbol)}${suffix}`;
}

export function useFundNavDashboard(symbol: string, enabled = true) {
  return useQuery({
    queryKey: ["fund-nav-dashboard", symbol],
    queryFn: async (): Promise<FundNavDashboard | null> => {
      const res = await apiGet<Envelope<FundNavDashboard>>(
        navUrl(symbol, "/dashboard")
      );
      return res?.success ? (res.data ?? null) : null;
    },
    enabled: enabled && Boolean(symbol),
    staleTime: 30_000,
    refetchInterval: 120_000,
  });
}

export function useCalculateFundNav(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (navType: string): Promise<FundNavRun | null> => {
      const res = await apiPost<Envelope<FundNavRun>>(navUrl(symbol, "/calculate"), {
        nav_type: navType,
        mode: "SHADOW",
      });
      return res?.success ? (res.data ?? null) : null;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-nav-dashboard", symbol] });
    },
  });
}

export function useReconcileFundNav(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (navType: string): Promise<FundNavReconciliation | null> => {
      const res = await apiPost<Envelope<FundNavReconciliation>>(
        navUrl(symbol, "/reconcile"),
        { nav_type: navType, mode: "SHADOW" }
      );
      return res?.success ? (res.data ?? null) : null;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-nav-dashboard", symbol] });
    },
  });
}

export interface FundClassNavClass {
  class_code: string;
  allocation_type?: string;
  net_assets: number | null;
  units: number | null;
  nav_per_unit: number | null;
  transfer_amount?: number | null;
  quality?: string | null;
}

export interface FundClassNav {
  fund_id: string;
  valuation_date: string;
  allocation_type: string;
  classes: FundClassNavClass[];
  details?: Record<string, unknown>;
}

export function useUpdateNavBreak(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      breakId: number;
      lifecycle: string;
      notes?: string;
    }): Promise<FundNavBreak | null> => {
      const res = await apiPatch<Envelope<FundNavBreak>>(
        `${NAV_BASE}/breaks/${input.breakId}`,
        { lifecycle: input.lifecycle, notes: input.notes }
      );
      return res?.success ? (res.data ?? null) : null;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-nav-dashboard", symbol] });
    },
  });
}

export function useFundClassNav(symbol: string, enabled = true) {
  return useQuery({
    queryKey: ["fund-class-nav", symbol],
    queryFn: async (): Promise<FundClassNav | null> => {
      const res = await apiGet<Envelope<FundClassNav>>(navUrl(symbol, "/class-nav"));
      return res?.success ? (res.data ?? null) : null;
    },
    enabled: enabled && Boolean(symbol),
    staleTime: 30_000,
  });
}

export function useCalculateClassNav(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<FundClassNav | null> => {
      const res = await apiPost<Envelope<FundClassNav>>(
        navUrl(symbol, "/class-nav/calculate"),
        {}
      );
      return res?.success ? (res.data ?? null) : null;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-class-nav", symbol] });
    },
  });
}
