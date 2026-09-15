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
  return toJalali(y, m, d);
}

/** Convert Jalali "YYYY/MM/DD" back to ISO "YYYY-MM-DD" */
export function jalaliToGregorian(jalaliStr: string): string | null {
  if (!jalaliStr || typeof jalaliStr !== "string") return null;
  const parts = jalaliStr.split("/");
  if (parts.length !== 3) return null;
  const [jy, jm, jd] = parts.map(Number);
  if (isNaN(jy) || isNaN(jm) || isNaN(jd)) return null;
  if (jm < 1 || jm > 12) return null;
  if (jd < 1 || jd > 31) return null;
  if (jm <= 6 && jd > 31) return null;
  if (jm > 6 && jd > 30) return null;
  let gy = jy + 1595;
  const days =
    -355668 +
    365 * jy +
    Math.floor(jy / 33) * 8 +
    Math.floor(((jy % 33) + 3) / 4) +
    jd +
    (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
  let gd = days % 365;
  if (gd < 0) {
    gy--;
    gd += 365;
  }
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let gm = 1;
  for (let i = 0; i < 12; i++) {
    if (gd < g_d_m[i]) break;
    gm = i + 1;
  }
  const gd2 = gd - (gm === 1 ? 0 : g_d_m[gm - 1]);
  return `${gy}-${String(gm).padStart(2, "0")}-${String(gd2).padStart(2, "0")}`;
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
