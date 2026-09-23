"use client";

/**
 * `/pre-buy/print/[sheetId]` — the A4 sheet as a route, not a modal.
 *
 * Keeping it a route means the browser prints the document itself: this page renders no
 * AppLayout, so there is no sidebar or header to hide behind print hacks.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Printer } from "lucide-react";
import type { BankQuestion } from "@/lib/pre-buy";
import { fetchExport, useCatalogue } from "@/lib/pre-buy-queries";
import { PrintSheet } from "@/components/prebuy/PrintSheet";

export default function PrintPage() {
  const { sheetId } = useParams<{ sheetId: string }>();
  const id = Number(sheetId);
  const data = useQuery({
    queryKey: ["pre-buy", "sheet", id, "export"],
    queryFn: () => fetchExport(id),
    enabled: Number.isFinite(id),
    retry: false,
  });
  // The sheet's own bank, not the equity default: the export arrives with the instrument
  // class it was judged as, and the catalogue re-keys when it does.
  const catalogue = useCatalogue(data.data?.instrument_type ?? "equity");

  const questionsByCode = new Map<string, BankQuestion>(
    (catalogue.data?.questions ?? []).map((q) => [q.code, q])
  );

  return (
    <main className="min-h-screen bg-white pb-10">
      <div data-screen-only className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-surface-900 px-4 py-2.5 text-white">
        <span className="text-[12px] font-bold">پیش‌نمایش چاپ برگهٔ تصمیم</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            disabled={!data.data}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-[11.5px] font-bold text-white hover:bg-primary-500 disabled:opacity-50"
          >
            <Printer className="w-3.5 h-3.5" /> چاپ
          </button>
          <Link
            href={`/pre-buy?symbol=${encodeURIComponent(data.data?.symbol ?? "")}`}
            className="rounded-lg border border-white/25 px-3 py-1.5 text-[11.5px] text-white/90 hover:bg-white/10"
          >
            بازگشت به برگه
          </Link>
        </div>
      </div>

      {data.isLoading && <p className="p-6 text-[12px] text-neutral-500">برگه در حال ساخت است…</p>}
      {data.isError && (
        <p className="p-6 text-[12px] text-red-700">
          این برگه ساخته نشد: {data.error instanceof Error ? data.error.message : "خطای نامشخص"}
        </p>
      )}
      {data.data && <PrintSheet data={data.data} questionsByCode={questionsByCode} />}
    </main>
  );
}
