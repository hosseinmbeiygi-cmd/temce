/**
 * Shared color utilities used across the app.
 */

/** Get a green-to-red color based on change value (-10 to +10 range). */
export function getChangeColor(change: number): string {
  const intensity = Math.min(Math.abs(change) / 5, 1);
  if (change > 0) {
    const r = Math.round(5 + (1 - intensity) * 55);
    const g = Math.round(120 + intensity * 77);
    const b = Math.round(60 + (1 - intensity) * 20);
    return `rgb(${r}, ${g}, ${b})`;
  } else if (change < 0) {
    const r = Math.round(180 + intensity * 55);
    const g = Math.round(30 + (1 - intensity) * 30);
    const b = Math.round(40 + (1 - intensity) * 20);
    return `rgb(${r}, ${g}, ${b})`;
  }
  return "rgb(60, 60, 80)";
}
