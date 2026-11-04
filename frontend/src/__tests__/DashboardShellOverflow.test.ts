// The aurora layer in the dashboard shell is `position: fixed` with a negative
// inset. `.page-enter` keeps a transform after its route animation, so that
// layer is positioned against `.page-enter` instead of the viewport and
// overflows the document by 18% of its width (≈345px at 1920px).
//
// This regression test locks the fix: the fixed aurora must start at inset 0
// (no negative bleed), while keeping the aurora animation.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");

function ruleBlock(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`).exec(CSS);
  return match?.[1] ?? "";
}

describe("dashboard shell horizontal overflow", () => {
  it("keeps the fixed aurora layer inside the viewport", () => {
    const aurora = ruleBlock(".dash-field::after");

    expect(aurora).toMatch(/position:\s*fixed/);
    expect(aurora).toMatch(/animation:\s*auroraDrift/);
    expect(aurora).toMatch(/inset:\s*0\s*;/);
    expect(aurora).not.toMatch(/inset:\s*-/);
  });

  it("puts the universal reset in @layer base so utilities can win", () => {
    // An unlayered `* { margin:0; padding:0 }` beats Tailwind v4's layered
    // utilities and neutralises every mx-*/px-*/py-* utility. The reset must
    // live in @layer base; utilities are in a later layer and win.
    expect(CSS).toMatch(
      /@layer\s+base\s*\{\s*\*\s*\{\s*margin:\s*0;\s*padding:\s*0;\s*box-sizing:\s*border-box;\s*\}\s*\}/,
    );
    expect(CSS).not.toMatch(
      /(^|\n)\*\s*\{\s*margin:\s*0;\s*padding:\s*0;\s*box-sizing:\s*border-box;\s*\}/m,
    );
  });

  it("clips the transformed page wrapper horizontally", () => {
    // `.page-enter` keeps a transform after pageRise; it is the containing
    // block for the fixed aurora. The drift animation still scales/translates
    // that layer (up to 5%), so the wrapper must clip horizontal overflow.
    const pageEnter = ruleBlock(".page-enter");

    expect(pageEnter).toMatch(/animation:\s*pageRise/);
    expect(pageEnter).toMatch(/overflow-x:\s*clip/);
  });
});
