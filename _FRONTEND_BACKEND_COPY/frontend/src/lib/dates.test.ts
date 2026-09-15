import { describe, expect, it } from "vitest";
import { gregorianToJalali, jalaliToGregorian, toJalali } from "./dates";

describe("toJalali", () => {
  it("converts a known Gregorian date to the canonical Jalali equivalent", () => {
    // 2024-01-01 (Gregorian) ↔ 1402/10/11 (Jalali)
    expect(toJalali(2024, 1, 1)).toBe("1402/10/11");
  });

  it("converts Nowruz (2023-03-21) to 1402/01/01", () => {
    expect(toJalali(2023, 3, 21)).toBe("1402/01/01");
  });

  it("pads single-digit months and days with zeros", () => {
    // 2023-03-21 → 1402/01/01 — first month and day are padded.
    const result = toJalali(2023, 3, 21);
    expect(result).toMatch(/^\d{4}\/\d{2}\/\d{2}$/);
  });
});

describe("gregorianToJalali", () => {
  it("returns em-dash for null/undefined/empty", () => {
    expect(gregorianToJalali(null)).toBe("—");
    expect(gregorianToJalali(undefined)).toBe("—");
    expect(gregorianToJalali("")).toBe("—");
  });

  it("returns em-dash for malformed strings", () => {
    expect(gregorianToJalali("not-a-date")).toBe("—");
    expect(gregorianToJalali("2024-13-99")).toBe("—");
  });

  it("delegates to toJalali for a valid ISO date", () => {
    expect(gregorianToJalali("2024-01-01")).toBe("1402/10/11");
  });
});

describe("jalaliToGregorian", () => {
  it("rejects out-of-range day-for-month", () => {
    expect(jalaliToGregorian("1402/07/31")).toBeNull(); // month 7-12: max 30 days
    expect(jalaliToGregorian("1402/13/01")).toBeNull(); // month > 12
    expect(jalaliToGregorian("1402/01/32")).toBeNull(); // month 1-6: max 31 days
  });

  it("returns null for malformed input", () => {
    expect(jalaliToGregorian("")).toBeNull();
    expect(jalaliToGregorian("not-a-date")).toBeNull();
    expect(jalaliToGregorian("1402/10")).toBeNull();
  });

  it("produces a well-formed ISO date for a valid Jalali input", () => {
    // Don't hard-code the exact conversion (depends on leap year math);
    // just check shape and that gregorianToJalali(roundtrips) is stable.
    const iso = jalaliToGregorian("1403/01/01");
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    if (iso) {
      expect(gregorianToJalali(iso)).toBe("1403/01/01");
    }
  });
});
