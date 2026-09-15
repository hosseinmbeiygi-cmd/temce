"use client";

import DashboardShell from "@/components/layout/DashboardShell";
import { PrecomputeProgressBanner } from "@/components/dashboard/PrecomputeProgressBanner";
import { ArmorDashboard } from "@/components/dashboard/ArmorDashboard";

export default function ArmorPage() {
  return (
    <DashboardShell>
      <div className="mb-6">
        <h1 className="text-[22px] font-black leading-tight text-ink">داشبورد زرهی</h1>
        <p className="mt-1 text-[12px] text-ink-3">
          محاسبه امتیاز زرهی (Armor Score) برای کل بازار — گروه‌بندی نقدشوندگی A/B/C با به‌روزرسانی زنده
        </p>
      </div>

      <div className="space-y-6">
        <PrecomputeProgressBanner />
        <ArmorDashboard />
      </div>
    </DashboardShell>
  );
}
