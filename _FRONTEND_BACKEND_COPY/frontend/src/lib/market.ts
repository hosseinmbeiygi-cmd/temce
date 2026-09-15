// Pure math over real price series — no synthetic data lives here.

export function sma(values: number[], period: number): number | null {
  if (values.length < period) return null;
  const slice = values.slice(-period);
  return slice.reduce((a, b) => a + b, 0) / period;
}

export function ema(values: number[], period: number): number | null {
  if (values.length < period) return null;
  const k = 2 / (period + 1);
  let acc = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (const value of values.slice(period)) acc = value * k + acc * (1 - k);
  return acc;
}

export function rsi(values: number[], period = 14): number | null {
  if (values.length < period + 1) return null;
  let gains = 0;
  let losses = 0;
  const start = values.length - period - 1;
  for (let i = start + 1; i < values.length; i += 1) {
    const delta = values[i] - values[i - 1];
    if (delta >= 0) gains += delta;
    else losses -= delta;
  }
  if (losses === 0) return 100;
  const rs = gains / period / (losses / period);
  return 100 - 100 / (1 + rs);
}

export function atr(highs: number[], lows: number[], closes: number[], period = 14): number | null {
  if (closes.length < period + 1) return null;
  const trs: number[] = [];
  for (let i = 1; i < closes.length; i += 1) {
    trs.push(Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1])));
  }
  return trs.slice(-period).reduce((a, b) => a + b, 0) / period;
}

export function returns(values: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < values.length; i += 1) out.push(values[i] / values[i - 1] - 1);
  return out;
}

/** Pearson correlation over the aligned tail of two return series. */
export function correlation(a: number[], b: number[]): number | null {
  const n = Math.min(a.length, b.length);
  if (n < 20) return null;
  const x = a.slice(-n);
  const y = b.slice(-n);
  const mx = x.reduce((s, v) => s + v, 0) / n;
  const my = y.reduce((s, v) => s + v, 0) / n;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < n; i += 1) {
    num += (x[i] - mx) * (y[i] - my);
    dx += (x[i] - mx) ** 2;
    dy += (y[i] - my) ** 2;
  }
  return dx > 0 && dy > 0 ? num / Math.sqrt(dx * dy) : null;
}

/** beta of asset returns vs market returns. */
export function beta(asset: number[], market: number[]): number | null {
  const n = Math.min(asset.length, market.length);
  if (n < 20) return null;
  const x = market.slice(-n);
  const y = asset.slice(-n);
  const mx = x.reduce((s, v) => s + v, 0) / n;
  const my = y.reduce((s, v) => s + v, 0) / n;
  let cov = 0;
  let varX = 0;
  for (let i = 0; i < n; i += 1) {
    cov += (x[i] - mx) * (y[i] - my);
    varX += (x[i] - mx) ** 2;
  }
  return varX > 0 ? cov / varX : null;
}

/** Resample a daily close series into calendar-week buckets (last close each week). */
export function weeklyCloses(values: number[]): number[] {
  const out: number[] = [];
  let week = -1;
  let last = 0;
  const today = new Date();
  for (let i = 0; i < values.length; i += 1) {
    const d = new Date(today);
    d.setDate(d.getDate() - (values.length - 1 - i));
    const yearStart = new Date(d.getFullYear(), 0, 1).getTime();
    const w = Math.floor((d.getTime() - yearStart) / (7 * 24 * 3600 * 1000));
    if (w !== week) {
      if (week !== -1) out.push(last);
      week = w;
    }
    last = values[i];
  }
  if (week !== -1) out.push(last);
  return out;
}

/** Multi-window trend validation computed from a real daily close series. */
export function windowSignals(closes: number[]): { label: string; bullish: boolean; score: number }[] {
  const windows: [string, number][] = [["1M", 22], ["3M", 66], ["6M", 132]];
  const out: { label: string; bullish: boolean; score: number }[] = [];
  for (const [label, len] of windows) {
    if (closes.length < len + 1) continue;
    const recent = closes.slice(-len);
    const momentum = recent[recent.length - 1] / recent[0] - 1;
    const aboveSma = sma(closes, Math.min(len, 50)) !== null && closes[closes.length - 1] > (sma(closes, Math.min(len, 50)) as number);
    const score = Math.max(0, Math.min(100, Math.round(50 + momentum * 400 + (aboveSma ? 12 : -12))));
    out.push({ label, bullish: score >= 55, score });
  }
  return out;
}
