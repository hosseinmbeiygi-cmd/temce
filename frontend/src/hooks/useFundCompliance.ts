"use client";

/**
 * 🛡 useFundCompliance — hooks برای FOF/مالیات/AML/حاکمیت/چرخه عمر/CSDI.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import type {
  AmlAlert,
  Committee,
  CsdiBreak,
  FofLatest,
  StrReport,
  TaxItem,
} from "@/lib/fund-compliance";

interface Envelope<T> {
  success: boolean;
  data: T;
}

const NAV_BASE = "/funds/v2/nav";
const COMP_BASE = "/funds/v2/compliance";

function url(base: string, symbol: string, suffix: string): string {
  return `${base}/${encodeURIComponent(symbol)}${suffix}`;
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>, symbol: string): void {
  qc.invalidateQueries({ queryKey: ["fund-compliance", symbol] });
  qc.invalidateQueries({ queryKey: ["fund-fof", symbol] });
}

// ── FOF ─────────────────────────────────────────────────────────────────────

export function useFofLatest(symbol: string) {
  return useQuery({
    queryKey: ["fund-fof", symbol],
    queryFn: async (): Promise<FofLatest | null> => {
      const res = await apiGet<Envelope<FofLatest>>(url(NAV_BASE, symbol, "/fof"));
      return res?.success ? (res.data ?? null) : null;
    },
    enabled: Boolean(symbol),
    staleTime: 60_000,
  });
}

export function useCalculateFof(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<FofLatest | null> => {
      const res = await apiPost<Envelope<FofLatest>>(url(NAV_BASE, symbol, "/fof/calculate"), {});
      return res?.success ? (res.data ?? null) : null;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fund-fof", symbol] }),
  });
}

// ── Tax ─────────────────────────────────────────────────────────────────────

export function useTaxSummary(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "tax"],
    queryFn: async (): Promise<{ items: TaxItem[]; total_tax: number }> => {
      const res = await apiGet<Envelope<{ items: TaxItem[]; total_tax: number }>>(
        url(COMP_BASE, symbol, "/tax/summary")
      );
      return res?.success ? res.data : { items: [], total_tax: 0 };
    },
    enabled: Boolean(symbol),
    staleTime: 60_000,
  });
}

export function useCalculateTax(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { tax_type: string; base_amount: number; period_label: string }) => {
      const res = await apiPost<Envelope<TaxItem>>(url(COMP_BASE, symbol, "/tax/calculate"), {
        ...input,
      });
      return res?.success ? res.data : null;
    },
    onSuccess: () => invalidateAll(qc, symbol),
  });
}

// ── AML ─────────────────────────────────────────────────────────────────────

export function useAmlAlerts(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "aml"],
    queryFn: async (): Promise<AmlAlert[]> => {
      const res = await apiGet<Envelope<{ alerts: AmlAlert[] }>>(
        url(COMP_BASE, symbol, "/aml/alerts?limit=20")
      );
      return res?.success ? (res.data?.alerts ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 30_000,
  });
}

export function useGenerateAmlAlerts(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiPost<Envelope<{ alerts_created: number; scanned: number }>>(
        url(COMP_BASE, symbol, "/aml/alerts/generate"),
        {}
      );
      return res?.success ? res.data : null;
    },
    onSuccess: () => invalidateAll(qc, symbol),
  });
}

export function useStrReports(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "str"],
    queryFn: async (): Promise<StrReport[]> => {
      const res = await apiGet<Envelope<{ reports: StrReport[] }>>(
        url(COMP_BASE, symbol, "/aml/str?limit=20")
      );
      return res?.success ? (res.data?.reports ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 30_000,
  });
}

export function useCreateStr(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { reason: string; amount?: number }) => {
      const res = await apiPost<Envelope<{ str_id: number }>>(
        url(COMP_BASE, symbol, "/aml/str"),
        { ...input }
      );
      return res?.success ? res.data : null;
    },
    onSuccess: () => invalidateAll(qc, symbol),
  });
}

// ── Governance / Lifecycle ──────────────────────────────────────────────────

export function useCommittees(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "committees"],
    queryFn: async (): Promise<Committee[]> => {
      const res = await apiGet<Envelope<{ committees: Committee[] }>>(
        url(COMP_BASE, symbol, "/committees")
      );
      return res?.success ? (res.data?.committees ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 120_000,
  });
}

export function useRecordCommittee(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { committee_type: string }) => {
      const res = await apiPost<Envelope<{ committee_id: number }>>(
        url(COMP_BASE, symbol, "/committees"),
        { ...input, members: [] }
      );
      return res?.success ? res.data : null;
    },
    onSuccess: () => invalidateAll(qc, symbol),
  });
}

export function useRptList(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "rpt"],
    queryFn: async (): Promise<Array<Record<string, unknown>>> => {
      const res = await apiGet<Envelope<{ transactions: Array<Record<string, unknown>> }>>(
        url(COMP_BASE, symbol, "/rpt?limit=20")
      );
      return res?.success ? (res.data?.transactions ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 60_000,
  });
}

export function useComplaints(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "complaints"],
    queryFn: async (): Promise<Array<Record<string, unknown>>> => {
      const res = await apiGet<Envelope<{ complaints: Array<Record<string, unknown>> }>>(
        url(COMP_BASE, symbol, "/complaints?limit=20")
      );
      return res?.success ? (res.data?.complaints ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 60_000,
  });
}

export function useProspectusVersions(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "prospectus"],
    queryFn: async (): Promise<Array<Record<string, unknown>>> => {
      const res = await apiGet<Envelope<{ versions: Array<Record<string, unknown>> }>>(
        url(COMP_BASE, symbol, "/prospectus?limit=20")
      );
      return res?.success ? (res.data?.versions ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 120_000,
  });
}

export function useLifecycleEvents(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "lifecycle"],
    queryFn: async (): Promise<Array<Record<string, unknown>>> => {
      const res = await apiGet<Envelope<{ events: Array<Record<string, unknown>> }>>(
        url(COMP_BASE, symbol, "/lifecycle?limit=20")
      );
      return res?.success ? (res.data?.events ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 120_000,
  });
}

// ── CSDI ────────────────────────────────────────────────────────────────────

export function useCsdiBreaks(symbol: string) {
  return useQuery({
    queryKey: ["fund-compliance", symbol, "csdi-breaks"],
    queryFn: async (): Promise<CsdiBreak[]> => {
      const res = await apiGet<Envelope<{ breaks: CsdiBreak[] }>>(
        url(COMP_BASE, symbol, "/csdi/breaks?limit=20")
      );
      return res?.success ? (res.data?.breaks ?? []) : [];
    },
    enabled: Boolean(symbol),
    staleTime: 60_000,
  });
}

export function useImportCsdiStatement(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      as_of_date: string;
      units_outstanding: number;
      source_ref: string;
    }) => {
      const res = await apiPost<Envelope<{ statement_id: number }>>(
        url(COMP_BASE, symbol, "/csdi/statements"),
        { ...input }
      );
      return res?.success ? res.data : null;
    },
    onSuccess: () => invalidateAll(qc, symbol),
  });
}

export function useReconcileCsdi(symbol: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<{
      status: string;
      units_diff: number | null;
      break_id: number | null;
    } | null> => {
      const res = await apiPost<Envelope<{
        status: string;
        units_diff: number | null;
        break_id: number | null;
      }>>(url(COMP_BASE, symbol, "/csdi/reconcile"), {});
      return res?.success ? res.data : null;
    },
    onSuccess: () => invalidateAll(qc, symbol),
  });
}
