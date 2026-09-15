"use client";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------------

export interface RealLegalData {
  buy_real_volume?: number;
  buy_legal_volume?: number;
  sell_real_volume?: number;
  sell_legal_volume?: number;
  buy_real_count?: number;
  buy_legal_count?: number;
  sell_real_count?: number;
  sell_legal_count?: number;
}

// ------ MiniRLBox (internal helper) ------------------------------------------------------------------------------------

function formatNum(v: number): string {
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString();
}

function MiniRLBox({ label, volume, count }: { label: string; volume: number; count: number }) {
  const isReal = label === "حقیقی";
  const bgColor = isReal ? "bg-amber-500/8" : "bg-indigo-500/8";
  const borderColor = isReal ? "border-amber-500/20" : "border-indigo-500/20";
  const textColor = isReal ? "text-amber-300" : "text-indigo-300";
  return (
    <div className={`${bgColor} ${borderColor} border rounded-lg p-2.5 text-center`}>
      <p className={`text-xs font-bold ${textColor} mb-1`}>{label}</p>
      <p className="font-mono font-bold text-surface-100 text-sm">
        {volume >= 1e6 ? (volume / 1e6).toFixed(1) + "M" : volume >= 1e3 ? (volume / 1e3).toFixed(0) + "K" : volume.toLocaleString()}
      </p>
      <p className="text-xs text-surface-500 mt-0.5">{count.toLocaleString()} نفر</p>
    </div>
  );
}

// ------ RealLegalCard ------------------------------------------------------------------------------------------------------------------------------

/**
 * Displays a real/legal person trade summary card.
 *
 * ```tsx
 * <RealLegalCard data={profile} />
 * ```
 */
export function RealLegalCard({ data }: { data: RealLegalData }) {
  const bRv = data.buy_real_volume ?? 0;
  const bLv = data.buy_legal_volume ?? 0;
  const sRv = data.sell_real_volume ?? 0;
  const sLv = data.sell_legal_volume ?? 0;
  const bRc = data.buy_real_count ?? 0;
  const bLc = data.buy_legal_count ?? 0;
  const sRc = data.sell_real_count ?? 0;
  const sLc = data.sell_legal_count ?? 0;

  const netReal = bRv - sRv;
  const netLegal = bLv - sLv;

  return (
    <div className="space-y-3 text-sm">
      {/* Header labels */}
      <div className="grid grid-cols-2 gap-2">
        <div className="text-center text-xs text-accent-emerald font-bold">خرید</div>
        <div className="text-center text-xs text-accent-rose font-bold">فروش</div>
      </div>
      {/* Buy / Sell side by side */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-2">
          <MiniRLBox label="حقیقی" volume={bRv} count={bRc} />
          <MiniRLBox label="حقوقی" volume={bLv} count={bLc} />
        </div>
        <div className="space-y-2">
          <MiniRLBox label="حقیقی" volume={sRv} count={sRc} />
          <MiniRLBox label="حقوقی" volume={sLv} count={sLc} />
        </div>
      </div>

      {/* Net flow */}
      <div className="pt-2 border-t border-surface-700/50 space-y-1">
        <div className="flex justify-between">
          <span className="text-surface-500 text-xs">خالص حقیقی:</span>
          <span className={`font-mono font-bold text-xs ${netReal >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
            {netReal >= 0 ? "+" : ""}{formatNum(netReal)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-500 text-xs">خالص حقوقی:</span>
          <span className={`font-mono font-bold text-xs ${netLegal >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
            {netLegal >= 0 ? "+" : ""}{formatNum(netLegal)}
          </span>
        </div>
      </div>
    </div>
  );
}
