// Phase 0 — C/D: هر قیمت باید برچسب کیفیت + منبع + زمان داشته باشد و متن
// سلب مسئولیت ثابت در UI دیده شود. این تست رگرسیونِ باگ قبلی را هم می‌گیرد:
// `quality_flag: "clean"` سطح snapshot به‌اشتباه «SAMPLE» نمایش داده می‌شد.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { AssetBlock, Snapshot } from "@/types/gold";

import GoldSummarySection from "@/app/gold/components/SummarySection";
import CoinBubbleTable from "@/app/gold/components/CoinBubbleTable";
import FundsPnavTable from "@/app/gold/components/FundsPnavTable";
import { GOLD_DISCLAIMER_TEXT, GoldDisclaimer } from "@/components/gold/GoldDisclaimer";

const asset = (overrides: Partial<AssetBlock> = {}): AssetBlock => ({
  value: 259_834_800,
  unit: "toman",
  asOf: "2026-10-26T08:59:00Z",
  source: "brsapi",
  quality: "LIVE",
  symbol: "IR_GOLD_18K",
  display_name: "طلای ۱۸ عیار",
  asset_type: "gold",
  market_price: 265_000_000,
  fair_value: 259_834_800,
  bubble_abs: 5_165_200,
  bubble_pct: 1.99,
  implied_usd: 2_695_000,
  quality_flag: "clean",
  ...overrides,
});

const snapshot = (overrides: Partial<Snapshot> = {}): Snapshot => ({
  snapshot_at: "2026-10-26T09:00:00Z",
  references: {
    xau_usd: 3998,
    usd_irt: 269_500,
    aed_irt: 245_000,
    aed_parity_usd: 3.6725,
    aed_gap_pct: 1.25,
    dxy_index: 102.5,
    source: "brsapi",
    age_seconds: 60,
    asOf: "2026-10-26T08:59:00Z",
    quality: "LIVE",
    unit: "toman",
  },
  gold: { gold_18k: asset() },
  coins: {},
  funds: [],
  score: {
    total: 62,
    decision: "YELLOW",
    components: {
      bubble: 0,
      bubble_reason: "",
      nav: 0,
      nav_reason: "",
      tsetmc: 0,
      tsetmc_reason: "",
      technical: 0,
      technical_reason: "",
      parity: 0,
      parity_reason: "",
      fund_flow: 0,
      fund_flow_reason: "",
    },
    hard_stop_active: false,
    hard_stop_reason: null,
  },
  quality_flag: "clean",
  ...overrides,
});

describe("Phase 0 trust labels", () => {
  it("renders the fixed disclaimer verbatim", () => {
    render(<GoldSummarySection snapshot={snapshot()} />);
    expect(screen.getByText(GOLD_DISCLAIMER_TEXT)).toBeInTheDocument();
    expect(GOLD_DISCLAIMER_TEXT).toMatch(/ابزار تحلیلی/);
    expect(GOLD_DISCLAIMER_TEXT).toMatch(/سفارش اجرا نمی‌کند/);
    expect(GOLD_DISCLAIMER_TEXT).toMatch(/توصیه قطعی خرید\/فروش نیست/);
  });

  it("shows LIVE with source and last-update time next to prices", () => {
    render(<GoldSummarySection snapshot={snapshot()} />);

    const live = screen
      .getAllByTestId("quality-badge")
      .filter((badge) => badge.getAttribute("data-quality") === "LIVE");
    expect(live.length).toBeGreaterThan(0);
    expect(screen.getAllByText(/منبع: brsapi/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/آخرین به‌روزرسانی:/).length).toBeGreaterThan(0);
    // 2026-10-26T08:59Z → 12:29 به وقت تهران
    expect(screen.getAllByText(/۱۲:۲۹/).length).toBeGreaterThan(0);
  });

  it("makes SAMPLE unmistakable and never claims it is live", () => {
    render(
      <GoldSummarySection
        snapshot={snapshot({ gold: { gold_18k: asset({ quality: "SAMPLE", source: "cache" }) } })}
      />,
    );

    const sample = screen
      .getAllByTestId("quality-badge")
      .find((badge) => badge.getAttribute("data-quality") === "SAMPLE");
    expect(sample).toBeDefined();
    expect(sample?.className).toMatch(/bg-rose-600/);
    expect(sample?.className).not.toMatch(/bg-emerald-500/);
    expect(screen.getByRole("alert")).toHaveTextContent(/دادهٔ نمونه یا آموزشی است/);
  });

  it("does not mislabel a legacy quality_flag=clean snapshot as SAMPLE", () => {
    render(<GoldSummarySection snapshot={snapshot({ gold: { gold_18k: asset() } })} />);

    // Badge از provenance هر قیمت می‌آید، نه از quality_flag سطح snapshot.
    expect(screen.queryByText("SAMPLE")).not.toBeInTheDocument();
    expect(screen.queryByText("EDUCATIONAL")).not.toBeInTheDocument();
  });

  it("handles age_seconds=null without inventing a timestamp", () => {
    const base = snapshot();
    render(
      <GoldSummarySection
        snapshot={{
          ...base,
          references: { ...base.references, age_seconds: null, asOf: null },
        }}
      />,
    );

    expect(screen.queryByText(/not set/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/زمان: نامشخص/).length).toBeGreaterThan(0);
  });

  it("renders no fabricated price when the snapshot is missing", () => {
    render(<GoldSummarySection />);
    expect(screen.getByText(/اسنپ‌شات بازار در دسترس نیست/)).toBeInTheDocument();
    expect(screen.queryByText(/۲٬۶۵۰|2650/)).not.toBeInTheDocument();
  });

  it("puts provenance on every coin row and a reference badge on the funds table", () => {
    render(
      <>
        <CoinBubbleTable
          data={[
            asset({
              symbol: "IR_COIN_EMAMI",
              display_name: "سکه امامی",
              asset_type: "coin",
              quality: "DELAYED",
              source: "brsapi",
              asOf: "2026-10-18T20:41:03Z",
            }),
          ]}
        />
        <FundsPnavTable
          data={[
            {
              symbol: "ZARFSHANG",
              fund_name: "زرافشان",
              nav_per_unit: 100_000,
              market_price: 105_000,
              bubble_pct: 5,
              bpr: 1.2,
              real_buy_value: 10,
              real_sell_value: 8,
              net_inflow: 2,
              nav_change_7d_pct: null,
            },
          ]}
          trust={snapshot().references}
        />
      </>,
    );

    const badges = screen.getAllByTestId("quality-badge");
    expect(
      badges.some((badge) => badge.getAttribute("data-quality") === "DELAYED"),
    ).toBe(true);
    expect(
      badges.some((badge) => badge.getAttribute("data-quality") === "LIVE"),
    ).toBe(true);
    expect(screen.getAllByText(/منبع: brsapi/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("مرجع دادهٔ صندوق:")).toBeInTheDocument();
    expect(screen.getAllByText(/آخرین به‌روزرسانی:/).length).toBeGreaterThanOrEqual(2);
  });
});

describe("GoldDisclaimer", () => {
  it("exposes the canonical text in banner variant", () => {
    render(<GoldDisclaimer variant="banner" />);
    expect(screen.getByRole("note", { name: "سلب مسئولیت" })).toHaveTextContent(
      GOLD_DISCLAIMER_TEXT,
    );
  });
});
