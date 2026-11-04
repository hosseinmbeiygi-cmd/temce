/**
 * نمونهٔ پاسخ ``GET /gold/assistant-rules`` — عیناً به‌شکل ``acceptance.yaml``.
 *
 * این fixture «وضعیت سروشده» را بازنمایی می‌کند تا تست‌ها مقدار عددی را از خود
 * کد نخوانند (وگرنه تست و منبع هاردکد هم‌زمان عوض می‌شوند و چیزی را ثابت نمی‌کنند).
 */
/**
 * شکل قابل‌دست‌کاری همان پاسخ — برای تست «پاسخ معیوب» بدون `any`: هر فیلدی که
 * تست خرابش می‌کند، اینجا نوعِ پذیرندهٔ مقدار خراب را هم دارد.
 */
export interface AssistantRulesDraft {
  version: string;
  fee_schedule: {
    version: string;
    last_updated: string;
    instruments: Record<
      string,
      {
        label_fa: string;
        fee_per_side: number | string | null;
        fee_cap_irr: number | string | null;
        tax_exempt: boolean;
        provenance: string;
        round_trip_fee_per_side: number | null;
        note?: string;
      }
    >;
  };
  signal_filter: {
    min_net_profit_pct: number | string;
    min_risk_reward: number | string;
    require_positive_ev: boolean;
    provenance: Record<string, string>;
  };
  market_hours: {
    sat_to_wed: { pre_open: string; open: string; close: string };
    thursday: { pre_open: string; open: string; close: string };
    friday_closed: boolean;
    price_band_pct: number | string;
    emergency_band_pcts: unknown[];
    settlement_days: number | string;
    provenance: string;
  };
}

/** کپیِ قابل‌تغییر پاسخ سروشده — تا تست هر فیلد را خراب کند. */
export function assistantRulesDraft(): AssistantRulesDraft {
  return structuredClone(ASSISTANT_RULES_PAYLOAD) as unknown as AssistantRulesDraft;
}

export const ASSISTANT_RULES_PAYLOAD = {
  version: "1.0",
  fee_schedule: {
    version: "1.0",
    last_updated: "1405-07-22",
    instruments: {
      commodity_fund: {
        label_fa: "صندوق کالایی طلا و نقره",
        fee_per_side: 0.0012,
        fee_cap_irr: null,
        tax_exempt: true,
        provenance: "assumption",
        round_trip_fee_per_side: 0.0024,
      },
      coin_certificate: {
        label_fa: "گواهی سپردهٔ سکهٔ طلا",
        fee_per_side: 0.00125,
        fee_cap_irr: 300000000,
        tax_exempt: true,
        provenance: "spec",
        round_trip_fee_per_side: 0.0025,
      },
      bullion_certificate: {
        label_fa: "گواهی سپردهٔ شمش و سایر",
        fee_per_side: 0.0024,
        fee_cap_irr: 450000000,
        tax_exempt: true,
        provenance: "spec",
        round_trip_fee_per_side: 0.0048,
      },
      futures: {
        label_fa: "آتی",
        fee_per_side: null,
        fee_cap_irr: null,
        tax_exempt: false,
        provenance: "unavailable",
        round_trip_fee_per_side: null,
      },
      option: {
        label_fa: "اختیار معامله",
        fee_per_side: null,
        fee_cap_irr: null,
        tax_exempt: false,
        provenance: "unavailable",
        round_trip_fee_per_side: null,
      },
    },
  },
  signal_filter: {
    min_net_profit_pct: 2.0,
    min_risk_reward: 2.0,
    require_positive_ev: true,
    provenance: { min_net_profit_pct: "spec", min_risk_reward: "assumption" },
  },
  market_hours: {
    sat_to_wed: { pre_open: "11:45", open: "12:00", close: "18:00" },
    thursday: { pre_open: "11:45", open: "12:00", close: "15:00" },
    friday_closed: true,
    price_band_pct: 10.0,
    emergency_band_pcts: [1, 2, 5],
    settlement_days: 1,
    provenance: "assumption",
  },
};
