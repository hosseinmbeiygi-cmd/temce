#!/usr/bin/env node
/**
 * Validate Mermaid diagram syntax using the real Mermaid parser.
 *
 * The mermaid UMD bundle (docs/assets/mermaid.min.js) needs a DOM, so we
 * evaluate it inside a jsdom sandbox and call mermaid.parse() on every
 * diagram from the manifest written by scripts/check_mermaid_blocks.py.
 *
 * Usage:
 *   node scripts/check_mermaid_syntax.cjs <manifest.json>
 *
 * Exit code 0 = all diagrams parse cleanly.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const MERMAID_LIB = path.join(ROOT, "docs", "assets", "mermaid.min.js");

function main() {
  const manifestPath = process.argv[2];
  if (!manifestPath) {
    console.error("Usage: node scripts/check_mermaid_syntax.cjs <manifest.json>");
    process.exit(2);
  }

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  } catch (err) {
    console.error(`Cannot read manifest ${manifestPath}: ${err.message}`);
    process.exit(2);
  }
  const diagrams = manifest.diagrams || [];

  if (!fs.existsSync(MERMAID_LIB)) {
    console.error(`Mermaid library not found: ${MERMAID_LIB}`);
    console.error(
      "Download it first: curl -L -o docs/assets/mermaid.min.js " +
        "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
    );
    process.exit(2);
  }

  // --- jsdom sandbox (mermaid needs a DOM even for parse-only) ------------
  let JSDOM;
  try {
    JSDOM = require("jsdom").JSDOM;
  } catch {
    // jsdom may only be installed inside frontend/node_modules
    try {
      JSDOM = require(path.join(ROOT, "frontend", "node_modules", "jsdom")).JSDOM;
    } catch {
      console.error(
        "jsdom is required. Install it with: npm i -D jsdom  (or cd frontend && npm ci)"
      );
      process.exit(2);
    }
  }

  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "http://localhost/",
    pretendToBeVisual: true,
  });
  const win = dom.window;
  const sandbox = {
    window: win,
    document: win.document,
    navigator: win.navigator,
    console,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    URL: win.URL,
    Blob: win.Blob,
  };
  sandbox.globalThis = sandbox;
  // jsdom's own globals that mermaid touches via bare identifiers:
  for (const key of ["HTMLElement", "SVGElement", "Element", "Node", "DOMParser"]) {
    if (win[key] !== undefined) sandbox[key] = win[key];
  }
  // Node primordials that jsdom's window does not expose:
  if (typeof globalThis.structuredClone === "function") {
    sandbox.structuredClone = globalThis.structuredClone;
  }
  vm.createContext(sandbox);

  let mermaid;
  try {
    const bundle = fs.readFileSync(MERMAID_LIB, "utf-8");
    vm.runInContext(bundle, sandbox, { filename: "mermaid.min.js" });
    mermaid = sandbox.window.mermaid || sandbox.mermaid;
  } catch (err) {
    console.error(`Failed to bootstrap mermaid in jsdom: ${err.message}`);
    process.exit(2);
  }
  if (!mermaid || typeof mermaid.parse !== "function") {
    console.error("mermaid.parse not available in the bundled library");
    process.exit(2);
  }

  runValidations(mermaid, diagrams).then((failures) => {
    if (failures.length) {
      console.error(`\nFAIL: ${failures.length} of ${diagrams.length} diagram(s) invalid:`);
      for (const f of failures) {
        console.error(`  - ${f.label}: ${f.error}`);
      }
      process.exit(1);
    }
    console.log(`All ${diagrams.length} mermaid diagram(s) passed syntax validation.`);
    process.exit(0);
  });
}

async function runValidations(mermaid, diagrams) {
  const failures = [];
  for (const d of diagrams) {
    const label = `${d.file} (diagram ${d.index})`;
    try {
      // suppressErrors:false => parse() rejects with the real parser message.
      const ok = await mermaid.parse(d.code || "", { suppressErrors: false });
      if (!ok) {
        failures.push({ label, error: "parse() returned falsy" });
      }
    } catch (err) {
      failures.push({ label, error: String(err && err.message ? err.message : err) });
      if (failures.length === 1 || process.env.MMD_VERBOSE) {
        console.error(`[INVALID] ${label}\n${d.code}\n`);
      }
    }
  }
  return failures;
}

main();
