"use client";

/**
 * 🧾 FundLedgerPanel — دفتر مالی دوطرفه در صفحه صندوق.
 *
 * - تراز آزمایشی با کنترل توازن
 * - ثبت حرکت واحد (صدور/ابطال/توزیع) → سند دوطرفه اتمیک
 * - آخرین اسناد و حرکت‌ها + سند برگشتی
 */

import { useState } from "react";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import {
  useFundJournalEntries,
  useFundTrialBalance,
  useFundUnitMovements,
  useRecordUnitMovement,
  useReverseJournalEntry,
} from "@/hooks/useFundLedger";
import {
  ACCOUNT_TYPE_LABELS,
  ENTRY_STATUS_LABELS,
  MOVEMENT_TYPE_LABELS,
  accountTone,
  formatAmount,
  movementTone,
} from "@/lib/fund-ledger";
import { labelOf, type Tone } from "@/lib/fund-nav";

const TONE_CLASS: Record<Tone, string> = {
  pos: "text-accent-emerald bg-accent-emerald/15",
  warn: "text-accent-amber bg-accent-amber/15",
  neg: "text-accent-rose bg-accent-rose/15",
  default: "text-surface-300 bg-surface-600/25",
};

function Chip({ label, tone = "default" }: { label: string; tone?: Tone }) {
  return (
    <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${TONE_CLASS[tone]}`}>
      {label}
    </span>
  );
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function FundLedgerPanel({ symbol }: { symbol: string }) {
  const [movementType, setMovementType] = useState("ISSUE");
  const [movementDate, setMovementDate] = useState(todayIso());
  const [units, setUnits] = useState("");
  const [price, setPrice] = useState("");

  const trial = useFundTrialBalance(symbol);
  const movements = useFundUnitMovements(symbol);
  const entries = useFundJournalEntries(symbol);
  const record = useRecordUnitMovement(symbol);
  const reverse = useReverseJournalEntry(symbol);

  async function handleRecord() {
    const parsedUnits = Number(units);
    const parsedPrice = price ? Number(price) : undefined;
    if (!parsedUnits || parsedUnits <= 0) {
      toast.error("تعداد واحد باید مثبت باشد");
      return;
    }
    if (movementType === "ISSUE" || movementType === "REDEEM") {
      if (!parsedPrice || parsedPrice <= 0) {
        toast.error("برای صدور/ابطال، قیمت هر واحد لازم است");
        return;
      }
    }
    try {
      const result = await record.mutateAsync({
        movement_type: movementType,
        movement_date: movementDate,
        units: parsedUnits,
        price_per_unit: parsedPrice,
      });
      if (result) {
        toast.success("حرکت واحد و سند دوطرفه ثبت شد");
        setUnits("");
        setPrice("");
      } else {
        toast.info("این حرکت قبلاً ثبت شده است (idempotent)");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در ثبت حرکت واحد");
    }
  }

  async function handleReverse(entryId: number) {
    try {
      await reverse.mutateAsync({ entryId });
      toast.success("سند برگشتی ثبت شد");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در ثبت سند برگشتی");
    }
  }

  const trialData = trial.data;
  const accounts = (trialData?.accounts ?? []).filter(
    (a) => a.debit !== 0 || a.credit !== 0
  );

  return (
    <Card
      title="دفتر مالی دوطرفه"
      actions={
        trialData ? (
          <div className="flex items-center gap-2">
            <Chip
              label={trialData.balanced ? "متوازن" : "نامتوازن"}
              tone={trialData.balanced ? "pos" : "neg"}
            />
            <span className="text-[10px] text-surface-500" dir="ltr">
              {formatAmount(trialData.total_debit)} / {formatAmount(trialData.total_credit)}
            </span>
          </div>
        ) : undefined
      }
    >
      {trial.isLoading && <Skeleton className="h-24 w-full rounded-xl" />}

      {!trial.isLoading && (
        <>
          {/* فرم ثبت حرکت واحد */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
            <select
              value={movementType}
              onChange={(e) => setMovementType(e.target.value)}
              className="text-[11px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-2 text-surface-300"
            >
              {Object.entries(MOVEMENT_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={movementDate}
              onChange={(e) => setMovementDate(e.target.value)}
              className="text-[11px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-2 text-surface-300"
              dir="ltr"
            />
            <input
              type="number"
              placeholder="تعداد واحد"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              className="text-[11px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-2 text-surface-300"
              dir="ltr"
            />
            <input
              type="number"
              placeholder="قیمت هر واحد (ریال)"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="text-[11px] bg-surface-800 border border-surface-700 rounded-lg px-2 py-2 text-surface-300"
              dir="ltr"
            />
            <button
              onClick={handleRecord}
              disabled={record.isPending}
              className="text-[11px] font-bold text-primary-300 hover:text-primary-200 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg px-3 py-2 transition-all disabled:opacity-50"
            >
              {record.isPending ? "در حال ثبت..." : "ثبت + سند دوطرفه"}
            </button>
          </div>

          {/* تراز آزمایشی */}
          <div className="mb-4">
            <p className="text-[11px] text-surface-400 mb-2">تراز آزمایشی</p>
            {accounts.length === 0 ? (
              <p className="text-[11px] text-surface-600 py-3 text-center">
                هنوز سندی ثبت نشده است؛ با ثبت حرکت واحد، تراز ساخته می‌شود.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="text-right py-1.5 px-2 font-normal">کد</th>
                      <th className="text-right py-1.5 px-2 font-normal">حساب</th>
                      <th className="text-right py-1.5 px-2 font-normal">نوع</th>
                      <th className="text-right py-1.5 px-2 font-normal">بدهکار</th>
                      <th className="text-right py-1.5 px-2 font-normal">بستانکار</th>
                      <th className="text-right py-1.5 px-2 font-normal">مانده</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((a) => (
                      <tr key={a.account_code} className="border-b border-surface-800/50">
                        <td className="py-1.5 px-2 font-mono text-surface-400" dir="ltr">
                          {a.account_code}
                        </td>
                        <td className="py-1.5 px-2 text-surface-200">{a.account_name}</td>
                        <td className="py-1.5 px-2">
                          <Chip
                            label={labelOf(ACCOUNT_TYPE_LABELS, a.account_type)}
                            tone={accountTone(a.account_type)}
                          />
                        </td>
                        <td className="py-1.5 px-2 font-mono text-surface-300" dir="ltr">
                          {formatAmount(a.debit)}
                        </td>
                        <td className="py-1.5 px-2 font-mono text-surface-300" dir="ltr">
                          {formatAmount(a.credit)}
                        </td>
                        <td className="py-1.5 px-2 font-mono text-surface-100" dir="ltr">
                          {formatAmount(a.balance)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* آخرین حرکت‌ها */}
          {(movements.data?.length ?? 0) > 0 && (
            <div className="mb-4">
              <p className="text-[11px] text-surface-400 mb-2">آخرین حرکت‌های واحد</p>
              <div className="space-y-1.5">
                {(movements.data ?? []).slice(0, 5).map((m) => (
                  <div
                    key={m.movement_id}
                    className="flex flex-wrap items-center justify-between gap-2 bg-surface-800/40 rounded-lg px-3 py-2 text-[11px]"
                  >
                    <div className="flex items-center gap-2">
                      <Chip
                        label={labelOf(MOVEMENT_TYPE_LABELS, m.movement_type)}
                        tone={movementTone(m.movement_type)}
                      />
                      <span className="text-surface-400" dir="ltr">
                        {formatAmount(m.units)} واحد
                      </span>
                      <span className="text-surface-500">{m.movement_date}</span>
                    </div>
                    <span className="font-mono text-surface-300" dir="ltr">
                      {formatAmount(m.amount)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* آخرین اسناد */}
          {(entries.data?.length ?? 0) > 0 && (
            <div>
              <p className="text-[11px] text-surface-400 mb-2">آخرین اسناد مالی</p>
              <div className="space-y-1.5">
                {(entries.data ?? []).slice(0, 5).map((e) => (
                  <div
                    key={e.entry_id}
                    className="flex flex-wrap items-center justify-between gap-2 bg-surface-800/40 rounded-lg px-3 py-2 text-[11px]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-surface-500" dir="ltr">
                        #{e.entry_id}
                      </span>
                      <span className="text-surface-300">{e.event_type}</span>
                      <Chip
                        label={labelOf(ENTRY_STATUS_LABELS, e.status)}
                        tone={e.status === "POSTED" ? "pos" : "warn"}
                      />
                      <span className="text-surface-600">{e.effective_at?.slice(0, 10)}</span>
                    </div>
                    {e.status === "POSTED" && (
                      <button
                        onClick={() => handleReverse(e.entry_id)}
                        disabled={reverse.isPending}
                        className="text-[10px] text-accent-amber bg-accent-amber/10 hover:bg-accent-amber/20 rounded-lg px-2 py-1 disabled:opacity-50"
                      >
                        سند برگشتی
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
