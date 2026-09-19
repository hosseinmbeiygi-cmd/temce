"use client";

/**
 * 🧾 useFundLedger — React Query hooks برای دفتر مالی دوطرفه.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import type { JournalEntry, TrialBalance, UnitMovement } from "@/lib/fund-ledger";

interface Envelope<T> {
  success: boolean;
  data: T;
  freshness?: string;
  fetched_from?: string;
}

const LEDGER_BASE = "/funds/v2/ledger";

function ledgerUrl(symbol: string, suffix: string): string {
  return `${LEDGER_BASE}/${encodeURIComponent(symbol)}${suffix}`;
}

export function useFundTrialBalance(symbol: string, enabled = true) {
  return useQuery({
    queryKey: ["fund-ledger-trial", symbol],
    queryFn: async (): Promise<TrialBalance | null> => {
      const res = await apiGet<Envelope<TrialBalance>>(ledgerUrl(symbol, "/trial-balance"));
      return res?.success ? (res.data ?? null) : null;
    },
    enabled: enabled && Boolean(symbol),
    staleTime: 30_000,
  });
}

export function useFundUnitMovements(symbol: string, enabled = true) {
  return useQuery({
    queryKey: ["fund-ledger-movements", symbol],
    queryFn: async (): Promise<UnitMovement[]> => {
      const res = await apiGet<Envelope<{ movements: UnitMovement[] }>>(
        ledgerUrl(symbol, "/unit-movements?limit=20")
      );
      return res?.success ? (res.data?.movements ?? []) : [];
    },
    enabled: enabled && Boolean(symbol),
    staleTime: 30_000,
  });
}

export function useFundJournalEntries(symbol: string, enabled = true) {
  return useQuery({
    queryKey: ["fund-ledger-entries", symbol],
    queryFn: async (): Promise<JournalEntry[]> => {
      const res = await apiGet<Envelope<{ entries: JournalEntry[] }>>(
        ledgerUrl(symbol, "/entries?limit=20")
      );
      return res?.success ? (res.data?.entries ?? []) : [];
    },
    enabled: enabled && Boolean(symbol),
    staleTime: 30_000,
  });
}

export function useRecordUnitMovement(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      movement_type: string;
      movement_date: string;
      units: number;
      price_per_unit?: number;
      reference?: string;
    }): Promise<UnitMovement | null> => {
      const res = await apiPost<Envelope<UnitMovement>>(
        ledgerUrl(symbol, "/unit-movements"),
        { ...input }
      );
      return res?.success ? (res.data ?? null) : null;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-ledger-trial", symbol] });
      qc.invalidateQueries({ queryKey: ["fund-ledger-movements", symbol] });
      qc.invalidateQueries({ queryKey: ["fund-ledger-entries", symbol] });
      qc.invalidateQueries({ queryKey: ["fund-nav-dashboard", symbol] });
    },
  });
}

export function useReverseJournalEntry(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { entryId: number; memo?: string }) => {
      const res = await apiPost<Envelope<{ entry_id: number }>>(
        `${LEDGER_BASE}/entries/${input.entryId}/reverse`,
        { memo: input.memo }
      );
      return res?.success ? res.data : null;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-ledger-trial", symbol] });
      qc.invalidateQueries({ queryKey: ["fund-ledger-entries", symbol] });
    },
  });
}
