// فза ۲ / بخش ۱ — لول ریلود سرویس‌ورکر روی /gold.
//
// علَّة لول: هر دو فایل SW در `install` `skipWaiting()` و در `activate`
// `clients.claim()` صدا می‌زنند. هر به‌روزرسانی SW ⇒ فعال‌شدن فوری ⇒ Claims
// کلاینت‌ها ⇒ `controllerchange` روی صفحه ⇒ possibility reload ⇒ لول.
//
// تست: منبع هر دو فایل SW را می‌خواند و ادعا می‌کند فراخوانی‌های Unguarded
// skipWaiting()/clients.claim() وجود ندارند. روی کد فعلی FALSE است (قرمز)؛
// بعد از حذف آن‌ها TRUE می‌شود (سبز).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = resolve(process.cwd(), "public");

function sourceOf(file: string): string {
  return readFileSync(resolve(ROOT, file), "utf8");
}

function hasUnguardedCall(source: string, call: string): boolean {
  // هر occurrenceِ call را می‌یابد؛ اگر داخل `if` نباشد ⇒ unguarded است.
  const regex = new RegExp(`self\\.${call}\\s*\\(`, "g");
  let match: RegExpExecArray | null;
  while ((match = regex.exec(source)) !== null) {
    const before = source.slice(0, match.index);
    // آخرین `if ` قبل از فراخوانی را می‌چینیم؛ اگر پس از آن `{` نبوده ⇒ غیرمحافظت‌شده
    const lastIf = before.lastIndexOf("if (");
    if (lastIf < 0) return true;
    const segment = before.slice(lastIf);
    if (!segment.includes("{")) return true;
  }
  return false;
}

describe("SW reload loop guard (Faza 2 / Section 1)", () => {
  it("golddesk-sw.js does not call skipWaiting() unguarded", () => {
    const src = sourceOf("golddesk-sw.js");
    expect(hasUnguardedCall(src, "skipWaiting")).toBe(false);
  });

  it("golddesk-sw.js does not call clients.claim() unguarded", () => {
    const src = sourceOf("golddesk-sw.js");
    expect(hasUnguardedCall(src, "clients.claim")).toBe(false);
  });

  it("sw.js does not call skipWaiting() unguarded", () => {
    const src = sourceOf("sw.js");
    expect(hasUnguardedCall(src, "skipWaiting")).toBe(false);
  });

  it("sw.js does not call clients.claim() unguarded", () => {
    const src = sourceOf("sw.js");
    expect(hasUnguardedCall(src, "clients.claim")).toBe(false);
  });
});
