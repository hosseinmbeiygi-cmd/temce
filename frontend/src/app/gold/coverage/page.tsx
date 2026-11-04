"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { GoldDisclaimer } from "@/components/gold/GoldDisclaimer";
import { formatAsOf } from "@/components/gold/DataTrustBadge";
import {
  getGoldFundMap,
  getGoldPlatforms,
  getGoldReturnsMatrix,
  getGoldTehranBoard,
} from "@/lib/goldApi";

import { FundMarketMap } from "./FundMarketMap";
import { PlatformsTable } from "./PlatformsTable";
import { ReturnsMatrix } from "./ReturnsMatrix";
import { SectionError, SectionLoading } from "./SectionFeedback";
import { TehranBoardTable } from "./TehranBoardTable";

/**
 * Phase 2 — پوشش بازار: تهران/بنکداری، بسترهای آنلاین (فقط قیمت)، ماتریس بازده،
 * نقشهٔ بازار صندوق‌ها.
 *
 * هیچ سفارش، کیف پول، پرداخت یا تحویلی روی این سطح وجود ندارد؛ `capabilities`
 * بک‌اند همهٔ این پرچم‌ها را false برمی‌گرداند و این صفحه دکمه‌ای خلاف آن نمی‌سازد.
 * هر بخش مستقل بارگذاری می‌شود تا خطای یک endpoint بقیهٔ پوشش را پنهان نکند.
 */
export default function MarketCoveragePage() {
  const [baseCurrency, setBaseCurrency] = useState<"IRR" | "USD">("IRR");
  const [sizeMetric, setSizeMetric] = useState<"trade_value" | "market_value">("trade_value");

  const tehran = useQuery({
    queryKey: ["gold", "tehran-board"],
    queryFn: getGoldTehranBoard,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
  });

  const platforms = useQuery({
    queryKey: ["gold", "platforms"],
    queryFn: getGoldPlatforms,
    refetchInterval: 300_000,
    refetchOnWindowFocus: false,
  });

  const matrix = useQuery({
    queryKey: ["gold", "returns-matrix", baseCurrency],
    queryFn: () => getGoldReturnsMatrix(baseCurrency),
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  });

  const fundMap = useQuery({
    queryKey: ["gold", "fund-map", sizeMetric],
    queryFn: () => getGoldFundMap(sizeMetric),
    refetchInterval: 120_000,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  });

  const capabilities = tehran.data?.capabilities ??
    platforms.data?.capabilities ??
    matrix.data?.capabilities ??
    fundMap.data?.capabilities ?? {
      orders: false,
      wallet: false,
      delivery: false,
      checkout: false,
      payment: false,
      preview_only: true,
    };

  return (
    <div className="space-y-8" dir="rtl" data-testid="market-coverage-page">
      <header className="space-y-2">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">پوشش بازار طلا</h1>
            <p className="mt-1 max-w-3xl text-xs leading-6 text-zinc-500">
              تختهٔ تهران و بنکداری، مقایسهٔ قیمت بسترهای آنلاین، ماتریس بازده دارایی‌ها و
              نقشهٔ بازار صندوق‌ها — همه فقط اطلاعاتی و با منبع/زمان/کیفیت. هیچ مسیر
              خرید، سفارش یا پرداخت در این صفحه وجود ندارد.
            </p>
          </div>
          {tehran.data && (
            <p className="text-[10px] text-zinc-500" data-testid="coverage-generated-at">
              تولید: {formatAsOf(tehran.data.generated_at) ?? "نامشخص"}
            </p>
          )}
        </div>
      </header>

      <section aria-label="تختهٔ تهران" data-testid="coverage-tehran">
        {tehran.isLoading && <SectionLoading label="تختهٔ تهران" />}
        {tehran.isError && (
          <SectionError
            error={tehran.error}
            label="تختهٔ تهران"
            testId="tehran-board-error"
          />
        )}
        {tehran.data && <TehranBoardTable data={tehran.data} />}
      </section>

      <section aria-label="بسترهای آنلاین" data-testid="coverage-platforms">
        {platforms.isLoading && <SectionLoading label="قیمت بسترهای آنلاین" />}
        {platforms.isError && (
          <SectionError
            error={platforms.error}
            label="قیمت بسترهای آنلاین"
            testId="platforms-error"
          />
        )}
        {platforms.data && <PlatformsTable data={platforms.data} />}
      </section>

      <section aria-label="ماتریس بازده" data-testid="coverage-returns">
        {matrix.isLoading && <SectionLoading label="ماتریس بازده" />}
        {matrix.isError && (
          <SectionError error={matrix.error} label="ماتریس بازده" testId="returns-matrix-error" />
        )}
        {matrix.data && (
          <ReturnsMatrix
            data={matrix.data}
            baseCurrency={baseCurrency}
            onBaseCurrencyChange={setBaseCurrency}
            pending={matrix.isFetching && !matrix.isLoading}
          />
        )}
      </section>

      <section aria-label="نقشهٔ بازار صندوق‌ها" data-testid="coverage-fund-map">
        {fundMap.isLoading && <SectionLoading label="نقشهٔ بازار صندوق‌ها" />}
        {fundMap.isError && (
          <SectionError error={fundMap.error} label="نقشهٔ بازار صندوق‌ها" testId="fund-map-error" />
        )}
        {fundMap.data && (
          <FundMarketMap
            data={fundMap.data}
            sizeMetric={sizeMetric}
            onSizeMetricChange={setSizeMetric}
            pending={fundMap.isFetching && !fundMap.isLoading}
          />
        )}
      </section>

      <p
        data-testid="coverage-capability-note"
        className="rounded-lg border border-zinc-800/70 bg-zinc-900/40 px-4 py-2 text-[11px] leading-6 text-zinc-400"
      >
        این صفحه فقط داده، تحلیل و مقایسه است؛ سفارش:{" "}
        {capabilities.orders ? "فعال" : "غیرفعال"} · کیف پول:{" "}
        {capabilities.wallet ? "فعال" : "غیرفعال"} · پرداخت:{" "}
        {capabilities.payment ? "فعال" : "غیرفعال"} · تحویل:{" "}
        {capabilities.delivery ? "فعال" : "غیرفعال"} · پیش‌نمایش محاسبات:{" "}
        {capabilities.preview_only ? "فعال" : "غیرفعال"}
      </p>
      <GoldDisclaimer variant="inline" />
    </div>
  );
}
