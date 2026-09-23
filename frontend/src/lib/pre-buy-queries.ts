"use client";

/**
 * Typed read/write layer for `/api/v1/pre-buy`.
 *
 * The backend answers in the `ApiResponse` envelope and reports domain errors as
 * HTTP 200 with `success:false`, so unwrapping has to inspect the body — a plain
 * `res.data` would swallow «برگهٔ ثبت‌شده قابل ویرایش نیست» as a null.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import type {
  Answer,
  Catalogue,
  Classification,
  Evaluation,
  EvidenceValue,
  InstrumentChoice,
  InstrumentType,
  ReviewRow,
  Sheet,
} from "@/lib/pre-buy";

interface Envelope<T> {
  success?: boolean;
  data?: T;
  error?: { message?: string } | string;
  message?: string;
}

function unwrap<T>(res: unknown): T {
  const body = (res ?? {}) as Envelope<T>;
  if (body.success === false) {
    const err = body.error;
    const msg = typeof err === "string" ? err : (err?.message ?? body.message ?? "درخواست ناموفق بود");
    throw new Error(msg);
  }
  return (body.data ?? res) as T;
}

export const preBuyKeys = {
  all: ["pre-buy"] as const,
  catalogue: (instrument: InstrumentType) => ["pre-buy", "catalogue", instrument] as const,
  instruments: () => ["pre-buy", "instruments"] as const,
  resolve: (symbol: string) => ["pre-buy", "resolve", symbol] as const,
  meta: () => ["pre-buy", "meta"] as const,
  evidence: (symbol: string, instrument: InstrumentType) =>
    ["pre-buy", "evidence", symbol, instrument] as const,
  sheets: () => ["pre-buy", "sheets"] as const,
  sheet: (id: number) => ["pre-buy", "sheet", id] as const,
  reviews: (id: number) => ["pre-buy", "sheet", id, "reviews"] as const,
};

export const enc = encodeURIComponent;

/** Which classes exist, and which of them actually have questions. Static per deploy. */
export function useInstruments(enabled = true) {
  return useQuery({
    queryKey: preBuyKeys.instruments(),
    queryFn: async () => unwrap<InstrumentChoice[]>(await apiGet<unknown>("/pre-buy/instruments")),
    enabled,
    staleTime: 60 * 60 * 1000,
  });
}

/**
 * What the stored tables say a symbol is. Read-only and never a write: the classification
 * only decides which bank the user may open, and `evidenced:false` must surface as a
 * question, not as a silently stock-shaped sheet.
 */
export function useResolveInstrument(symbol: string | null) {
  return useQuery({
    queryKey: preBuyKeys.resolve(symbol ?? ""),
    queryFn: async () => unwrap<Classification>(await apiGet<unknown>(`/pre-buy/resolve/${enc(symbol ?? "")}`)),
    enabled: Boolean(symbol && symbol.length > 1),
    staleTime: 5 * 60 * 1000,
  });
}

/** The bank is static, versioned content — one fetch per instrument per session is enough. */
export function useCatalogue(instrument: InstrumentType = "equity") {
  return useQuery({
    queryKey: preBuyKeys.catalogue(instrument),
    queryFn: async () =>
      unwrap<Catalogue>(await apiGet<unknown>(`/pre-buy/catalogue?instrument=${instrument}`)),
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    retry: 0,
  });
}

export function useSheet(id: number | null) {
  return useQuery({
    queryKey: preBuyKeys.sheet(id ?? -1),
    queryFn: async () => unwrap<Sheet>(await apiGet<unknown>(`/pre-buy/sheets/${id}`)),
    enabled: id !== null && id > 0,
    staleTime: 0,
  });
}

export function useSheets(enabled = true) {
  return useQuery({
    queryKey: preBuyKeys.sheets(),
    queryFn: async () => unwrap<Sheet[]>(await apiGet<unknown>("/pre-buy/sheets")),
    enabled,
    staleTime: 15_000,
  });
}

export function useReviews(sheetId: number | null) {
  return useQuery({
    queryKey: preBuyKeys.reviews(sheetId ?? -1),
    queryFn: async () => unwrap<ReviewRow[]>(await apiGet<unknown>(`/pre-buy/sheets/${sheetId}/reviews`)),
    enabled: sheetId !== null && sheetId > 0,
  });
}

/** Live evidence for a symbol with no sheet yet — what the tab can show before login. */
export function useSymbolEvidence(symbol: string | null, instrument: InstrumentType = "equity") {
  return useQuery({
    queryKey: preBuyKeys.evidence(symbol ?? "", instrument),
    queryFn: async () =>
      unwrap<{ symbol: string; instrument: InstrumentType; evidence: Record<string, EvidenceValue> }>(
        await apiGet<unknown>(`/pre-buy/evidence/${enc(symbol ?? "")}?instrument=${instrument}`)
      ),
    enabled: Boolean(symbol),
    staleTime: 60_000,
    retry: 0,
  });
}

export interface AnswerPatch {
  answers: Record<string, Answer | null>;
  refreshEvidence?: boolean;
}

const toWire = (patch: AnswerPatch) => ({
  answers: patch.answers,
  refresh_evidence: patch.refreshEvidence ?? true,
});

/**
 * Opens (or resumes) the single draft a user may hold for one symbol.
 *
 * `POST /sheets` is get-or-create, so re-entering the tab never forks a second sheet —
 * the partial unique index on (user, symbol) WHERE status='DRAFT' enforces it in the DB.
 * Omitting `instrument` lets the backend classify the symbol; it refuses rather than
 * defaulting, so the failure arrives as a Persian domain error through `unwrap`.
 */
export function useOpenSheet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: string | { symbol: string; instrument?: InstrumentType }) => {
      const body = typeof input === "string" ? { symbol: input } : input;
      return unwrap<Sheet>(await apiPost<unknown>("/pre-buy/sheets", body));
    },
    onSuccess: (sheet) => {
      qc.setQueryData(preBuyKeys.sheet(sheet.id), sheet);
      void qc.invalidateQueries({ queryKey: preBuyKeys.sheets() });
    },
  });
}

/** Re-pointing a draft at another bank; `ignoredAnswers` counts the answers that stop applying. */
export function useSetInstrument(sheetId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (instrument: InstrumentType) =>
      unwrap<Sheet & { ignoredAnswers: number }>(
        await apiPost<unknown>(`/pre-buy/sheets/${sheetId}/instrument`, { instrument })
      ),
    onSuccess: (sheet) => {
      qc.setQueryData(preBuyKeys.sheet(sheet.id), sheet);
      void qc.invalidateQueries({ queryKey: preBuyKeys.sheets() });
    },
    retry: 0,
  });
}

/**
 * Persists answers and returns the server's verdict.
 *
 * Every save re-resolves the evidence by default: the whole point of the sheet is that
 * a decision is bound to the figures visible while it was made, so a stale P/E must not
 * sit next to a fresh answer.
 */
export function useSaveAnswers(sheetId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: AnswerPatch) =>
      unwrap<{ sheet: Sheet; evaluation: Evaluation }>(
        await apiPut<unknown>(`/pre-buy/sheets/${sheetId}/answers`, toWire(patch))
      ),
    onSuccess: ({ sheet }) => {
      qc.setQueryData(preBuyKeys.sheet(sheet.id), sheet);
      void qc.invalidateQueries({ queryKey: preBuyKeys.sheets() });
    },
  });
}

/** What-if evaluation: same body, nothing written. */
export function useEvaluate(sheetId: number | null) {
  return useMutation({
    mutationFn: async (patch: AnswerPatch) =>
      unwrap<{ sheet: Sheet; evaluation: Evaluation }>(
        await apiPost<unknown>(`/pre-buy/sheets/${sheetId}/evaluate`, toWire(patch))
      ),
  });
}

export function useSubmitSheet(sheetId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (statement: string | null) =>
      unwrap<{ review_id: number; verdict: string; input_hash: string }>(
        await apiPost<unknown>(`/pre-buy/sheets/${sheetId}/submit`, { statement })
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: preBuyKeys.sheet(sheetId ?? -1) });
      void qc.invalidateQueries({ queryKey: preBuyKeys.sheets() });
      void qc.invalidateQueries({ queryKey: preBuyKeys.reviews(sheetId ?? -1) });
    },
  });
}

export function useReopenSheet(sheetId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap<Sheet>(await apiPost<unknown>(`/pre-buy/sheets/${sheetId}/reopen`, {})),
    onSuccess: (sheet) => {
      qc.setQueryData(preBuyKeys.sheet(sheet.id), sheet);
      void qc.invalidateQueries({ queryKey: preBuyKeys.sheets() });
    },
  });
}

export interface ExportRow {
  code: string;
  stage: number;
  text: string;
  stopper: boolean;
  answer: string | null;
  numbers: Record<string, number>;
  note: string | null;
  evidence: { key: string; label: string; source: string; unit: string; value: number | string | null; status: string; asOf: string | null; declared: boolean; note: string }[];
}

export interface ExportPayload {
  symbol: string;
  instrument_name: string | null;
  instrument_type: InstrumentType;
  instrument_label: string;
  /** Which table decided the type, or «انتخاب کاربر» — printed so the claim is auditable. */
  instrument_basis: string | null;
  bank_version: string;
  verdict: string;
  detail: Evaluation | null;
  input_hash: string | null;
  submitted_at: string | null;
  /** Answer codes left from another instrument bank; excluded from `rows`, named in the printout. */
  orphanAnswerCodes: string[];
  rows: ExportRow[];
}

export async function fetchExport(sheetId: number): Promise<ExportPayload> {
  return unwrap<ExportPayload>(await apiGet<unknown>(`/pre-buy/sheets/${sheetId}/export`));
}
