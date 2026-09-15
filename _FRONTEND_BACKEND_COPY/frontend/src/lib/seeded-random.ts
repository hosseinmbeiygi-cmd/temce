/**
 * Deterministic pseudo-random number generator (LCG — Numerical Recipes).
 *
 * Used for mock/demo chart data so renders stay **pure** and **stable**:
 * the same seed always produces the same sequence, which keeps fallback
 * charts from flickering/re-randomizing on every re-render.
 */
export function seededRandom(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/** Derive a numeric seed from a string (e.g. a symbol name). */
export function stringSeed(value: string): number {
  let seed = 0;
  for (let i = 0; i < value.length; i++) {
    seed = (seed * 31 + value.charCodeAt(i)) >>> 0;
  }
  return seed || 1;
}
