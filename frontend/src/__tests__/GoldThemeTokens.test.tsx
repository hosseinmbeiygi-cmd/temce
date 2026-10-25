// F1 — درخت gold کاملاً بر پایهٔ متغیرهای --gd-* نوشته شده، ولی اگر آن‌ها در
// globals.css تعریف نشده باشند، `var()` مقدار نامعتبر می‌گیرد و declare نادیده
// گرفته می‌شود (پس‌زمینهٔ شفاف، متن بی‌کنتراست). ThemeProvider فقط
// data-theme را ست می‌کند، پس تعریف‌ها باید زیر سلکتورهای [data-theme="…"]
// باشند. این تست همان قرارداد را بین فایل CSS و مصرف‌کننده‌ها قفل می‌کند.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ThemeProvider, ThemeToggle } from "@/components/gold/ThemeProvider";

// vitest این فایل را با cwd = پوشهٔ frontend اجرا می‌کند؛ در محیط jsdom
// import.meta.url آدرس http می‌دهد، پس مسیر واقعی از cwd گرفته می‌شود.
const SRC = resolve(process.cwd(), "src");
const GLOBALS = readFileSync(SRC + "/app/globals.css", "utf8");

/** هر ۱۲ توکنی که قرارداد F1 الزام می‌کند. */
const REQUIRED_TOKENS = [
  "--gd-bg",
  "--gd-bg-2",
  "--gd-bg-3",
  "--gd-border",
  "--gd-text",
  "--gd-text-2",
  "--gd-text-3",
  "--gd-accent",
  "--gd-accent-2",
  "--gd-success",
  "--gd-warn",
  "--gd-danger",
];

const THEMES = ["dark", "light", "gold"] as const;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = `${dir}/${name}`;
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(tsx|ts)$/.test(name)) out.push(full);
  }
  return out;
}

/** تمام فایل‌های درخت gold که مصرف‌کنندهٔ این توکن‌ها هستند. */
const GOLD_FILES = [...walk(`${SRC}/app/gold`), ...walk(`${SRC}/components/gold`)];

/**
 * بلوک‌های تم را از CSS بیرون می‌کشد: سلکتورهایی که [data-theme="x"] دارند و
 * اعلام‌های --gd-* داخلشان. بدنهٔ بلوک با شمارش براکت پیدا می‌شود.
 */
function gdTokensByTheme(css: string): Record<string, Set<string>> {
  const result: Record<string, Set<string>> = {};
  const blockRe = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = blockRe.exec(css)) !== null) {
    const selector = match[1];
    const body = match[2];
    const themes = [...selector.matchAll(/\[data-theme="([a-z]+)"\]/g)].map((m) => m[1]);
    if (themes.length === 0) continue;
    const declared = [...body.matchAll(/(--gd-[a-z0-9-]+)\s*:/g)].map((m) => m[1]);
    for (const theme of themes) {
      const set = result[theme] ?? new Set<string>();
      declared.forEach((t) => set.add(t));
      result[theme] = set;
    }
  }
  return result;
}

function usedTokens(): Set<string> {
  const used = new Set<string>();
  for (const file of GOLD_FILES) {
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(/var\(\s*(--gd-[a-z0-9-]+)/g)) used.add(m[1]);
  }
  return used;
}

describe("GoldDesk theme tokens (F1)", () => {
  afterEach(() => {
    document.documentElement.removeAttribute("data-theme");
  });

  it("defines every required --gd-* token under each of the three themes", () => {
    const byTheme = gdTokensByTheme(GLOBALS);
    for (const theme of THEMES) {
      const defined = byTheme[theme];
      expect(defined, `هیچ بلوک [data-theme="${theme}"] با توکن --gd-* پیدا نشد`).toBeDefined();
      const missing = REQUIRED_TOKENS.filter((t) => !defined.has(t));
      expect(missing, `تم ${theme} این توکن‌ها را ندارد: ${missing.join(", ")}`).toEqual([]);
    }
  });

  it("leaves no var(--gd-*) in the gold tree undefined", () => {
    const byTheme = gdTokensByTheme(GLOBALS);
    const used = usedTokens();
    // اطمینان از خودِ تست: باید مصرف‌کننده پیدا کرده باشد، وگرنه تست الکی سبز است.
    expect(used.size).toBeGreaterThan(0);
    for (const theme of THEMES) {
      const defined = byTheme[theme] ?? new Set<string>();
      const undef = [...used].filter((t) => !defined.has(t));
      expect(undef, `در تم ${theme} تعریف نشده‌اند: ${undef.join(", ")}`).toEqual([]);
    }
  });

  it("never uses the gold theme's gradient --gd-bg where a flat color is required", () => {
    // در تم gold مقدار --gd-bg یک linear-gradient است؛ در جای color یا
    // background-color یا border-color معنا ندارد و اعلام را می‌شکند.
    for (const file of GOLD_FILES) {
      const text = readFileSync(file, "utf8");
      const bad = [...text.matchAll(/(?:^|[\s{,])(?:color|backgroundColor|borderColor)\s*:\s*["']?var\(--gd-bg\)/g)];
      expect(bad, `${file} از --gd-bg (گرادیان در تم gold) به‌جای رنگ تخت استفاده می‌کند`).toHaveLength(0);
    }
  });

  it("ThemeProvider writes the data-theme attribute the CSS blocks key on", async () => {
    // بدون این رفتار، هر بلوک [data-theme="…"] بی‌اثر است.
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    await screen.findByRole("button");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    fireEvent.click(screen.getByRole("button"));
    await screen.findByText("روشن");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
