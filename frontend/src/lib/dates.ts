/**
 * Shared Jalali (Shamsi) date utilities.
 * Converts Gregorian dates to Jalali for display.
 */

/** Convert Gregorian (y,m,d) to Jalali string "YYYY/MM/DD" */
export function toJalali(gy: number, gm: number, gd: number): string {
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days =
    355666 +
    365 * gy +
    Math.floor((gy2 + 3) / 4) -
    Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) +
    gd +
    g_d_m[gm - 1];
  let jy = -1595 + 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  let jm: number;
  let jd: number;
  if (days < 186) {
    jm = 1 + Math.floor(days / 31);
    jd = 1 + (days % 31);
  } else {
    jm = 7 + Math.floor((days - 186) / 30);
    jd = 1 + ((days - 186) % 30);
  }
  return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
}

/** Convert ISO date string "YYYY-MM-DD" to Jalali "YYYY/MM/DD" */
export function gregorianToJalali(isoDate: string | null | undefined): string {
  if (!isoDate || isoDate.length < 10) return "—";
  const [y, m, d] = isoDate.split("-").map(Number);
  if (isNaN(y) || isNaN(m) || isNaN(d)) return "—";
  // Range guard: "2024-13-99" parses to finite numbers but month 13 indexes
  // g_d_m out of bounds and NaN propagates into the result.
  if (m < 1 || m > 12 || d < 1 || d > 31) return "—";
  return toJalali(y, m, d);
}

/**
 * Convert Jalali "YYYY/MM/DD" back to ISO "YYYY-MM-DD".
 *
 * The previous closed-form inverse (gy = jy + 1595 ...) was mathematically
 * wrong and produced nonsense dates (e.g. 1403/01/01 → year 2377). Instead of
 * duplicating leap-year machinery, this inverts the (test-pinned) forward
 * converter with a day-accurate binary search: zero-padded Jalali strings
 * compare lexicographically in chronological order, so the search finds the
 * unique Gregorian day whose toJalali equals the input — roundtrip parity is
 * guaranteed by construction. Range ≈ Gregorian 1799..2093 (Jalali 1177..1471).
 */
export function jalaliToGregorian(jalaliStr: string): string | null {
  if (!jalaliStr || typeof jalaliStr !== "string") return null;
  const parts = jalaliStr.split("/");
  if (parts.length !== 3) return null;
  const [jy, jm, jd] = parts.map(Number);
  if (isNaN(jy) || isNaN(jm) || isNaN(jd)) return null;
  if (jy < 1 || jm < 1 || jm > 12) return null;
  if (jd < 1 || jd > 31) return null;
  if (jm <= 6 && jd > 31) return null;
  if (jm > 6 && jd > 30) return null;

  const target = `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
  let lo = Date.UTC(1799, 0, 1);
  let hi = Date.UTC(2093, 0, 1);
  while (hi - lo > 1) {
    const mid = Math.floor((lo + hi) / 2);
    const dt = new Date(mid);
    const j = toJalali(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate());
    if (j < target) lo = mid;
    else hi = mid;
  }
  const hit = new Date(hi);
  const y = hit.getUTCFullYear();
  const m = hit.getUTCMonth() + 1;
  const d = hit.getUTCDate();
  if (toJalali(y, m, d) !== target) return null; // no such Jalali day exists
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/**
 * Format any ISO date string to Jalali for display.
 * Input: "2025-01-15" or "2025-01-15T10:30:00" or full ISO
 * Output: "1403/10/25"
 */
export function formatDateShamsi(d: string | null | undefined): string {
  if (!d) return "—";
  const datePart = d.length >= 10 ? d.slice(0, 10) : d;
  return gregorianToJalali(datePart);
}

/** Format ISO datetime to HH:MM time string */
export function formatTime(t: string | null | undefined): string {
  if (!t) return "—";
  // If it's a full ISO string, extract time part
  if (t.includes("T")) {
    const timePart = t.split("T")[1];
    return timePart ? timePart.substring(0, 5) : "—";
  }
  return t.length >= 5 ? t.substring(0, 5) : t;
}

/** Format ISO datetime to full Jalali date + time: "1403/10/25 14:30" */
export function formatDateTimeShamsi(dt: string | null | undefined): string {
  if (!dt) return "—";
  const datePart = dt.slice(0, 10);
  const timePart = dt.includes("T") ? dt.split("T")[1]?.substring(0, 5) : null;
  const jalaliDate = gregorianToJalali(datePart);
  return timePart ? `${jalaliDate} ${timePart}` : jalaliDate;
}
