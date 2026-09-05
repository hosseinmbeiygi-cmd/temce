// API client برای سرویس ارز (apps/currency_service)
// مسیرها زیر /api/v1/currency — rewrite در next.config.ts به پورت 8002.
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import type {
  CreatePositionInput,
  CurrencyOverview,
  PositionListResponse,
} from "@/types/currency";

export function getCurrencyOverview(): Promise<CurrencyOverview> {
  return apiGet<CurrencyOverview>("/currency/overview");
}

export function getCurrencySignals() {
  return apiGet<{
    timestamp: string;
    kill_switch_active: boolean;
    count: number;
    signals: CurrencyOverview["signals"];
  }>("/currency/signals");
}

export function listPositions(): Promise<PositionListResponse> {
  return apiGet<PositionListResponse>("/currency/positions");
}

export interface CreatedPosition {
  id: number;
  user_id: string;
  asset_type: CreatePositionInput["asset_type"];
  entry_price: number;
  volume: number;
  entry_date: string;
  created_at: string;
  note: string | null;
}

export function createPosition(input: CreatePositionInput): Promise<CreatedPosition> {
  return apiPost<CreatedPosition>(
    "/currency/positions",
    input as unknown as Record<string, unknown>
  );
}

export function deletePosition(id: number) {
  return apiDelete<{ deleted: boolean; id: number }>(
    `/currency/positions/${id}`
  );
}
