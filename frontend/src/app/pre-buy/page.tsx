"use client";

/**
 * `/pre-buy` — the decision-sheet workbench.
 *
 * The symbol page is where a sheet gets filled; this page is where the archive lives:
 * every sheet the user holds, its verdict, and the review history. Both render the same
 * `DecisionSheet`, so there is one form and one gate, not two that can disagree.
 */

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ClipboardCheck, LogIn, Plus, Search } from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth-context";
import type { Sheet } from "@/lib/pre-buy";
import { useCatalogue, useSheets } from "@/lib/pre-buy-queries";
import { DecisionSheet } from "@/components/prebuy/DecisionSheet";
import { Chip, fmt, Panel, toneText, type Tone } from "@/components/prebuy/ui";
import { cn } from "@/lib/cn";

export default function PreBuyPage() {
  return (
    <AppLayout
      title="برگهٔ تصمیم پیش از خرید"
      subtitle="قضاوت در سرور محاسبه می‌شود، نه در مرورگر شما — شمار سؤال و مرحله را بانک همان نوع ابزار می‌دهد"
    >
      <Suspense fallback={<div className="p-6 text-[12px] text-surface-500">در حال بارگذاری…</div>}>
        <Workbench />
      </Suspense>
    </AppLayout>
  );
}

function Workbench() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const params = useSearchParams();
  const catalogue = useCatalogue();
  const sheets = useSheets(isAuthenticated);
  const [typed, setTyped] = useState(params.get("symbol") ?? "");
  const [symbol, setSymbol] = useState(params.get("symbol") ?? "");

  const rows = useMemo(() => sheets.data ?? [], [sheets.data]);

  useEffect(() => {
    const fromUrl = params.get("symbol");
    if (fromUrl) setSymbol(fromUrl);
  }, [params]);

  if (authLoading) {
    return <div className="p-6 text-[12px] text-surface-500">در حال بررسی نشست…</div>;
  }

  if (!isAuthenticated) {
    return (
      <Panel title="برگهٔ تصمیم برای هر کاربر جدا نگه داشته می‌شود" desc="پاسخ‌ها، شواهد و قضاوت هر برگه در حساب شما ثبت می‌شود.">
        <Link
          href={`/auth/login?redirect=${encodeURIComponent("/pre-buy")}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3.5 py-2 text-[12px] font-bold text-white hover:bg-primary-500"
        >
          <LogIn className="w-4 h-4" /> ورود به حساب
        </Link>
      </Panel>
    );
  }

  return (
    <div className="space-y-3">
      <div className="glass-card flex flex-wrap items-center gap-2 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const value = typed.trim();
            if (value) setSymbol(value);
          }}
          className="flex min-w-[240px] flex-1 items-center gap-2"
        >
          <Search className="w-4 h-4 shrink-0 text-surface-500" />
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="نماد را وارد کنید — مثال: فولاد"
            className="min-w-0 flex-1 rounded-lg border border-surface-700 bg-surface-900/60 px-2.5 py-1.5 text-[12px] text-surface-100 outline-none focus:border-primary-500"
          />
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-[11.5px] font-bold text-white hover:bg-primary-500"
          >
            <Plus className="w-3.5 h-3.5" /> برگهٔ این نماد
          </button>
        </form>
        <span className="text-[10px] text-surface-600">
          بانک {catalogue.data?.bankVersion ?? "—"} — {fmt(catalogue.data?.total)} سؤال
        </span>
      </div>

      {symbol ? (
        <DecisionSheet key={symbol} symbol={symbol} />
      ) : (
        <Panel title="نمادی انتخاب نشده" desc="یک نماد وارد کنید یا از برگه‌های زیر یکی را باز کنید.">
          <p className="text-[11px] leading-relaxed text-surface-500">
            در صفحهٔ هر نماد هم می‌توانید همین برگه را باز کنید: تب «برگهٔ خرید».
          </p>
        </Panel>
      )}

      <Panel
        title="برگه‌های من"
        desc="هر نماد حداکثر یک برگهٔ باز دارد؛ برگهٔ ثبت‌شده قفل است و در تاریخچه می‌ماند."
      >
        {sheets.isLoading ? (
          <p className="text-[11px] text-surface-500">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <p className="text-[11px] text-surface-500">هنوز برگه‌ای نساخته‌اید.</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {rows.map((sheet) => (
              <SheetCard key={sheet.id} sheet={sheet} active={sheet.symbol === symbol} onOpen={setSymbol} />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function SheetCard({ sheet, active, onOpen }: { sheet: Sheet; active: boolean; onOpen: (symbol: string) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(sheet.symbol)}
        className={cn(
          "w-full rounded-xl border p-2.5 text-right transition-colors",
          active ? "border-primary-500/50 bg-primary-600/10" : "border-surface-700/70 bg-surface-800/40 hover:bg-surface-800"
        )}
      >
        <span className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-[12px] font-extrabold text-surface-100">
            <ClipboardCheck className="w-3.5 h-3.5 text-surface-500" />
            {sheet.symbol}
          </span>
          <Chip label={sheet.status === "DRAFT" ? "باز" : sheet.status === "SUBMITTED" ? "بایگانی" : "رهاشده"} tone={sheet.status === "DRAFT" ? "accent" : "muted"} />
        </span>
        <span className={cn("mt-1.5 block text-[10.5px] leading-relaxed", toneText(verdictTone(sheet.verdict)))}>
          {sheet.detail?.verdictLabel ?? "—"}
        </span>
        <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-surface-700">
          <span className="block h-full rounded-full bg-primary-500" style={{ width: `${sheet.completion_pct}%` }} />
        </span>
        <span className="mt-1 block text-[9.5px] text-surface-600" dir="ltr">
          {fmt(sheet.completion_pct)}٪
        </span>
      </button>
    </li>
  );
}

const verdictTone = (v: Sheet["verdict"]): Tone =>
  v === "cleared" ? "pos" : v === "vetoed" ? "neg" : v === "not_started" ? "muted" : "warn";
