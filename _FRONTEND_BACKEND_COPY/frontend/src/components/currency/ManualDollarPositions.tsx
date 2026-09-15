"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusCircle, Trash2 } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { createPosition, deletePosition, listPositions } from "@/lib/currencyApi";
import { cn } from "@/lib/cn";
import type { AssetType } from "@/types/currency";

function fmt(n: number): string {
  return n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

/** پوزیشن‌های نقدی دستی — persist شده سمت سرور (PostgreSQL) با PnL زنده. */
export function ManualDollarPositions() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["currency-positions"],
    queryFn: listPositions,
    refetchInterval: 15_000,
  });

  const [assetType, setAssetType] = useState<AssetType>("CASH_USD");
  const [entryPrice, setEntryPrice] = useState("");
  const [volume, setVolume] = useState("");
  const [error, setError] = useState<string | null>(null);

  const addMut = useMutation({
    mutationFn: createPosition,
    onSuccess: () => {
      setError(null);
      setEntryPrice("");
      setVolume("");
      qc.invalidateQueries({ queryKey: ["currency-positions"] });
    },
    onError: (e: Error) => setError(e.message || "خطا در ثبت پوزیشن"),
  });

  const delMut = useMutation({
    mutationFn: deletePosition,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["currency-positions"] }),
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    const price = parseFloat(entryPrice);
    const vol = parseFloat(volume);
    if (!price || !vol || price <= 0 || vol <= 0) {
      setError("قیمت و حجم باید عدد مثبت باشند");
      return;
    }
    addMut.mutate({ asset_type: assetType, entry_price: price, volume: vol });
  };

  const inputCls =
    "h-9 rounded-lg border border-zinc-700/60 bg-zinc-800/60 px-3 text-xs text-zinc-100 outline-none focus:ring-2 focus:ring-primary-500/40";

  return (
    <Card title="پوزیشن‌های نقدی ثبت‌شده دستی">
      <form onSubmit={handleAdd} className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={assetType}
          onChange={(e) => setAssetType(e.target.value as AssetType)}
          className={inputCls}
        >
          <option value="CASH_USD">دلار نقدی</option>
          <option value="USDT">تتر (USDT)</option>
        </select>
        <input
          type="number"
          inputMode="decimal"
          placeholder="قیمت ورود (تومان)"
          value={entryPrice}
          onChange={(e) => setEntryPrice(e.target.value)}
          className={cn(inputCls, "w-36")}
        />
        <input
          type="number"
          inputMode="decimal"
          placeholder="حجم (واحد/دلار)"
          value={volume}
          onChange={(e) => setVolume(e.target.value)}
          className={cn(inputCls, "w-32")}
        />
        <button
          type="submit"
          disabled={addMut.isPending}
          className="flex h-9 items-center gap-1 rounded-md bg-primary-600 px-3 text-xs font-bold text-white hover:bg-primary-700 disabled:opacity-50"
        >
          <PlusCircle className="h-4 w-4" />
          {addMut.isPending ? "در حال ثبت…" : "افزودن"}
        </button>
      </form>

      {error && <div className="mb-3 rounded-lg bg-rose-500/10 p-2 text-xs text-rose-600 dark:text-rose-400">{error}</div>}

      {isLoading ? (
        <p className="py-6 text-center text-xs opacity-60">در حال بارگذاری پوزیشن‌ها…</p>
      ) : !data || data.positions.length === 0 ? (
        <p className="py-6 text-center text-xs opacity-60">
          هیچ پوزیشن نقدی ثبت نشده است. از فرم بالا معاملات دستی خود را وارد کنید.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-right text-xs opacity-70">
                <th className="py-2 pr-1 font-medium">دارایی</th>
                <th className="py-2 font-medium">تاریخ ثبت</th>
                <th className="py-2 font-medium">حجم</th>
                <th className="py-2 font-medium">قیمت ورود</th>
                <th className="py-2 font-medium">نرخ فعلی</th>
                <th className="py-2 font-medium">سود/زیان (تومان)</th>
                <th className="py-2 text-center font-medium">بازده</th>
                <th className="py-2 text-center font-medium">حذف</th>
              </tr>
            </thead>
            <tbody>
              {data.positions.map((p) => (
                <tr key={p.id} className="border-b last:border-0">
                  <td className="py-2.5 pr-1 font-semibold">
                    {p.asset_type === "CASH_USD" ? "دلار نقدی" : "تتر (USDT)"}
                  </td>
                  <td className="py-2.5 text-xs opacity-70">{p.entry_date}</td>
                  <td className="py-2.5 tabular-nums">{fmt(p.volume)}</td>
                  <td className="py-2.5 tabular-nums">{fmt(p.entry_price)}</td>
                  <td className="py-2.5 tabular-nums">{fmt(p.current_price)}</td>
                  <td
                    className={cn(
                      "py-2.5 font-medium tabular-nums",
                      p.pnl_toman >= 0 ? "text-emerald-500" : "text-rose-500"
                    )}
                  >
                    {p.pnl_toman >= 0 ? "+" : ""}
                    {fmt(p.pnl_toman)}
                  </td>
                  <td
                    className={cn(
                      "py-2.5 text-center font-mono tabular-nums",
                      p.return_pct >= 0 ? "text-emerald-500" : "text-rose-500"
                    )}
                  >
                    {p.return_pct >= 0 ? "+" : ""}
                    {p.return_pct.toFixed(2)}%
                  </td>
                  <td className="py-2.5 text-center">
                    <button
                      onClick={() => delMut.mutate(p.id)}
                      disabled={delMut.isPending}
                      className="rounded p-1 opacity-60 transition hover:bg-rose-500/10 hover:text-rose-500 hover:opacity-100"
                      aria-label={`حذف پوزیشن ${p.id}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
