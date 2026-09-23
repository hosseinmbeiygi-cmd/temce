"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import FundWorkspace from "@/components/funds/FundWorkspace";

export default function FundDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params?.symbol ?? "");

  return (
    <AppLayout title={symbol ? `میز کار صندوق ${symbol}` : "میز کار صندوق"} subtitle="NAV، بازار، سبد، عملکرد، دفتر، انطباق و حسابرسی — در تب‌های جدا">
      <Suspense
        fallback={
          <div className="space-y-3">
            <Skeleton className="h-24 w-full rounded-2xl" />
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-64 w-full rounded-2xl" />
          </div>
        }
      >
        <FundWorkspace symbol={symbol} />
      </Suspense>
    </AppLayout>
  );
}
