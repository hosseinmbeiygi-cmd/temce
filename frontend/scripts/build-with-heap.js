#!/usr/bin/env node
/**
 * Cross-platform build wrapper: guarantees `next build` runs with enough heap.
 *
 * Why: the TypeScript-check worker of `next build` OOM-crashed
 * ("Committing semi space failed") at the default heap on this project —
 * ~120 route modules + heavy deps. POSIX inline env (`VAR=x cmd`) does not
 * work on cmd.exe/PowerShell, so the wrapper sets it programmatically and
 * spawns the real build. Works identically on Windows (Git Bash/cmd),
 * Linux, and macOS.
 *
 * Override the default with FRONTEND_BUILD_HEAP_MB; an explicit
 * --max-old-space-size already present in NODE_OPTIONS wins.
 */
const { spawn } = require("child_process");

const DEFAULT_HEAP_MB = 6144;

function resolveHeapMb() {
  const explicit = /--max-old-space-size=(\d+)/.exec(process.env.NODE_OPTIONS || "");
  if (explicit) {
    const mb = Number(explicit[1]);
    console.log(`[build] NODE_OPTIONS already sets heap: ${mb} MB (leaving as-is)`);
    return null;
  }
  const custom = parseInt(process.env.FRONTEND_BUILD_HEAP_MB || "", 10);
  const mb = Number.isFinite(custom) && custom > 0 ? custom : DEFAULT_HEAP_MB;
  console.log(`[build] Setting --max-old-space-size=${mb} MB`);
  return mb;
}

const mb = resolveHeapMb();
const nodeOpts = (process.env.NODE_OPTIONS || "").trim();
const merged = mb
  ? `${nodeOpts ? nodeOpts + " " : ""}--max-old-space-size=${mb}`
  : nodeOpts;

const useShell = process.platform === "win32";
const child = spawn("next", ["build"], {
  stdio: "inherit",
  shell: useShell,
  env: { ...process.env, NODE_OPTIONS: merged },
});

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
