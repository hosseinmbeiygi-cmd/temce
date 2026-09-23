import type { StrategyAnalysis } from './types';

// Latin digits (en-US): option tables render dir="ltr" font-mono cells and
// Persian glyphs break the tabular mono alignment — same terminal convention
// as src/lib/market-format.ts. Persian digits belong to prose (faNum).
const nf = new Intl.NumberFormat('en-US');

export function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined || !isFinite(n)) return '—';
  return nf.format(n);
}

export function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || !isFinite(n)) return '—';
  const sign = n > 0 ? '+' : '';
  return sign + n.toFixed(digits) + '٪';
}

export function riskColor(r: string): string {
  switch (r) {
    case 'low': return 'text-accent-emerald';
    case 'medium': return 'text-accent-amber';
    case 'high': return 'text-accent-rose';
    case 'very_high': return 'text-accent-rose';
    default: return 'text-surface-400';
  }
}

export function riskBg(r: string): string {
  switch (r) {
    case 'low': return 'bg-accent-emerald/10 border-accent-emerald/30';
    case 'medium': return 'bg-accent-amber/10 border-accent-amber/30';
    case 'high': return 'bg-accent-rose/10 border-accent-rose/30';
    case 'very_high': return 'bg-accent-rose/20 border-accent-rose/50';
    default: return 'bg-surface-800/50 border-surface-700/50';
  }
}

export function riskLabel(r: string): string {
  const labels: Record<string, string> = {
    low: 'کم',
    medium: 'متوسط',
    high: 'زیاد',
    very_high: 'خیلی زیاد',
  };
  return labels[r] || r;
}

export function marketLabel(m: string): string {
  const labels: Record<string, string> = {
    bullish: 'صعودی',
    bearish: 'نزولی',
    neutral: 'خنثی',
    volatile: 'نوسان',
    neutral_bullish: 'خنثی-صعودی',
    neutral_low_vol: 'خنثی کم نوسان',
    volatile_bullish: 'نوسان صعودی',
    volatile_bearish: 'نوسان نزولی',
    bullish_mild: 'صعودی ملایم',
    bearish_mild: 'نزولی ملایم',
    directional: 'جهت‌دار',
    any: 'هر شرایطی',
  };
  return labels[m] || m;
}

export function PayoffDiagram({ analysis, width = 600, height = 300 }: { analysis: StrategyAnalysis; width?: number; height?: number }) {
  if (!analysis?.profit_at_expiry?.length) return null;
  const data = analysis.profit_at_expiry;
  const prices = data.map(d => d.price);
  const profits = data.map(d => d.profit);
  const minP = Math.min(...profits);
  const maxP = Math.max(...profits);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const pad = 40;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const xS = (p: number) => pad + ((p - minPrice) / (maxPrice - minPrice || 1)) * w;
  const yS = (p: number) => pad + ((maxP - p) / (maxP - minP || 1)) * h;
  const pts = data.map(d => xS(d.price) + ',' + yS(d.profit)).join(' ');
  const zeroY = yS(0);
  const isProfitable = maxP > 0;
  const chartColor = isProfitable ? '#22c55e' : '#ef4444';

  const fillPoints = xS(data[0].price) + ',' + zeroY + ' ' + data.map(d => xS(d.price) + ',' + yS(d.profit)).join(' ') + ' ' + xS(data[data.length - 1].price) + ',' + zeroY;

  return (
    <svg width='100%' viewBox='0 0 600 300' className='bg-surface-900 rounded-lg' style={{ direction: 'ltr' }}>
      {/* zero line */}
      <line x1={pad} y1={zeroY} x2={width - pad} y2={zeroY} stroke='#475569' strokeWidth={1} strokeDasharray='4' />
      {/* y-axis */}
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke='#475569' strokeWidth={1} />
      {/* x-axis bottom */}
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke='#475569' strokeWidth={1} />

      {/* fill area */}
      <polygon points={fillPoints} fill={isProfitable ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)'} />
      {/* payoff line */}
      <polyline points={pts} fill='none' stroke={chartColor} strokeWidth={2.5} strokeLinejoin='round' strokeLinecap='round' />

      {/* breakeven markers */}
      {analysis.break_even?.map((be, i) => {
        const bx = xS(be);
        return (
          <g key={i}>
            <circle cx={bx} cy={zeroY} r={4} fill='#fbbf24' stroke='#000' strokeWidth={1.5} />
            <line x1={bx} y1={zeroY - 8} x2={bx} y2={zeroY + 8} stroke='#fbbf24' strokeWidth={1.5} />
          </g>
        );
      })}

      {/* max profit / loss labels */}
      <text x={width - pad} y={pad + 12} fill='#22c55e' fontSize={11} textAnchor='end' fontFamily='monospace'>
        {maxP > 0 ? 'بیشترین سود: ' + fmt(maxP) : ''}
      </text>
      <text x={width - pad} y={height - pad - 8} fill='#ef4444' fontSize={11} textAnchor='end' fontFamily='monospace'>
        {minP < 0 ? 'بیشترین ضیان: ' + fmt(minP) : ''}
      </text>
    </svg>
  );
}
