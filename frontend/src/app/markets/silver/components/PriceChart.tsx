"use client";

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface Props {
  candles: Candle[];
  height?: number;
  emptyHint?: string;
}

export default function PriceChart({ candles, height = 300, emptyHint }: Props) {
  if (candles.length < 2) {
    return (
      <div className="grid h-44 place-items-center rounded-xl bg-soft text-center text-xs text-ink-3">
        {emptyHint ?? "داده تاریخی کافی برای نمودار موجود نیست."}
      </div>
    );
  }

  const w = 800;
  const padX = 64;
  const padY = 20;
  const plotR = w - 20;
  const highs = candles.map((c) => c.high);
  const lows = candles.map((c) => c.low);
  const max = Math.max(...highs);
  const min = Math.min(...lows);
  const range = max - min || 1;
  const x = (i: number) => padX + (i / (candles.length - 1)) * (plotR - padX);
  const y = (v: number) => padY + (1 - (v - min) / range) * (height - padY * 2);
  const cw = Math.max(1.5, ((plotR - padX) / candles.length) * 0.6);

  const last = candles[candles.length - 1];
  const first = candles[0];
  const trendUp = last.close >= first.close;
  const lineColor = trendUp ? "#10b981" : "#f43f5e";
  const linePts = candles.map((c, i) => `${x(i).toFixed(1)},${y(c.close).toFixed(1)}`).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const dateStep = Math.max(1, Math.floor(candles.length / 5));

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet" style={{ direction: "ltr" }}>
        <defs>
          <linearGradient id="silver-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
          </linearGradient>
        </defs>

        {ticks.map((t) => {
          const yy = padY + t * (height - padY * 2);
          return <line key={t} x1={padX} x2={plotR} y1={yy} y2={yy} stroke="#64748b" strokeOpacity={0.15} strokeWidth={1} />;
        })}

        <polygon points={`${padX},${height - padY} ${linePts} ${x(candles.length - 1)},${height - padY}`} fill="url(#silver-area)" />

        {candles.map((c, i) => {
          const up = c.close >= c.open;
          const col = up ? "#10b981" : "#f43f5e";
          const xx = x(i);
          const bodyTop = y(Math.max(c.open, c.close));
          const bodyBottom = y(Math.min(c.open, c.close));
          return (
            <g key={`${c.time}-${i}`}>
              <line x1={xx} x2={xx} y1={y(c.high)} y2={y(c.low)} stroke={col} strokeWidth={1} />
              <rect x={xx - cw / 2} y={bodyTop} width={cw} height={Math.max(1, bodyBottom - bodyTop)} fill={col} rx={0.5} />
            </g>
          );
        })}

        <line x1={padX} x2={plotR} y1={y(last.close)} y2={y(last.close)} stroke={lineColor} strokeDasharray="5 4" strokeWidth={1} />
        <text x={plotR + 2} y={y(last.close) + 3} fill={lineColor} fontSize={10} fontFamily="monospace" textAnchor="start">
          {last.close.toLocaleString("en-US")}
        </text>

        {ticks.map((t) => {
          const v = max - t * range;
          const yy = padY + t * (height - padY * 2);
          return (
            <text key={`y-${t}`} x={padX - 6} y={yy + 3} fill="#94a3b8" fontSize={10} fontFamily="monospace" textAnchor="end">
              {v >= 1000 ? Math.round(v).toLocaleString("en-US") : v.toFixed(2)}
            </text>
          );
        })}

        {candles.map((c, i) =>
          i % dateStep === 0 || i === candles.length - 1 ? (
            <text key={`x-${c.time}-${i}`} x={x(i)} y={height - 4} fill="#94a3b8" fontSize={9} textAnchor="middle">
              {c.time?.slice(5) ?? ""}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}
