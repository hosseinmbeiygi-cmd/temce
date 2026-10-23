import fs from "fs";

// v2: batch-fix @typescript-eslint/no-unused-vars in src/ with safe strategies.
//  - imports: remove specifier (drop line if it empties)
//  - single-line `type X = ...` declarations
//  - useState destructuring pairs
//  - single-line, bracket-balanced, side-effect-free const/let with <=1 reference
// Everything else is reported as skipped for manual review.
const data = JSON.parse(fs.readFileSync("eslint_report.json", "utf8"));
const SKIP = ["public", "__tests__"];
let fixed = 0;
const log = [], skipped = [];

for (const f of data) {
  if (!f.messages.length) continue;
  const norm = f.filePath.replace(/\\/g, "/");
  if (SKIP.some((d) => norm.includes(`/${d}/`))) continue;
  const src = fs.readFileSync(f.filePath, "utf8");
  const lines = src.split("\n");
  let changed = false;

  const msgs = [...f.messages]
    .filter((m) => m.ruleId === "@typescript-eslint/no-unused-vars")
    .sort((a, b) => b.line - a.line);

  for (const m of msgs) {
    const isDefined = /defined but never used/.test(m.message);
    const isAssigned = /assigned a value but never used/.test(m.message);
    if (!isDefined && !isAssigned) continue;
    const name = m.message.split(" ")[0].replace(/'/g, "");
    const line = lines[m.line - 1];
    if (line === undefined) continue;
    const t = line.trim();
    const rel = norm.split("/").slice(-3).join("/");

    // -- import lines ------------------------------------------------------
    if (isDefined && (t.startsWith("import ") || /^import\b/.test(t))) {
      let nl = line;
      const pats = [
        new RegExp(`\\s*\\b${name}\\b,`),
        new RegExp(`,\\s*\\b${name}\\b`),
        new RegExp(`\\{\\s*\\b${name}\\b\\s*\\}`),
        new RegExp(`\\b${name}\\b,\\s*`),
      ];
      for (const p of pats) {
        const before = nl;
        nl = nl.replace(p, "");
        if (nl !== before) break;
      }
      // default import: "import X from ..." -> drop whole line
      if (nl === line && new RegExp(`^import\\s+${name}\\s+from\\b`).test(t)) nl = "";
      // line emptied of meaning -> drop
      if (/\{\s*\}/.test(nl) || /^import\s+from\s+/.test(nl.trim())) nl = "";
      if (nl !== line) {
        lines[m.line - 1] = nl;
        changed = true; fixed++;
        log.push(`import  ${rel}:${m.line} ${name}`);
        continue;
      }
    }

    // -- single-line type alias -------------------------------------------
    if (isDefined && new RegExp(`^(export\\s+)?type\\s+${name}\\b`).test(t) && t.endsWith(";")) {
      lines[m.line - 1] = "";
      changed = true; fixed++;
      log.push(`type    ${rel}:${m.line} ${name}`);
      continue;
    }

    // -- useState destructuring -------------------------------------------
    const usm = t.match(/^(const|let)\s+\[(.*?)\]\s*=\s*useState/);
    if (isAssigned && usm) {
      const inner = usm[2];
      const parts = inner.split(",").map((s) => s.trim());
      if (parts.length === 2) {
        const [a, b] = parts;
        if (a === name) {
          lines[m.line - 1] = line.replace(`[${inner}]`, `[, ${b}]`);
          changed = true; fixed++;
          log.push(`useSt-v ${rel}:${m.line} ${name}`);
          continue;
        }
        if (b === name) {
          lines[m.line - 1] = line.replace(`[${inner}]`, `[${a}, ]`);
          changed = true; fixed++;
          log.push(`useSt-s ${rel}:${m.line} ${name}`);
          continue;
        }
      }
    }

    // -- single-line const/let, no side effects ----------------------------
    if (isAssigned && /^(const|let)\s+/.test(t) && t.endsWith(";")) {
      const bal = ["(", ")", "{", "}", "[", "]"].every(() => true);
      const counts = {
        "(": (t.match(/\(/g) || []).length, ")": (t.match(/\)/g) || []).length,
        "{": (t.match(/\{/g) || []).length, "}": (t.match(/\}/g) || []).length,
        "[": (t.match(/\[/g) || []).length, "]": (t.match(/\]/g) || []).length,
      };
      const balanced = counts["("] === counts[")"] && counts["{"] === counts["}"] && counts["["] === counts["]"];
      const risky = /\b(fetch|api|axios|localStorage|sessionStorage|document|window|console|dispatch|router|mutate|refetch)\b/.test(t);
      const uses = (src.match(new RegExp(`\\b${name}\\b`, "g")) || []).length;
      if (bal && balanced && !risky && uses <= 1) {
        lines[m.line - 1] = "";
        changed = true; fixed++;
        log.push(`const   ${rel}:${m.line} ${name}`);
        continue;
      }
    }

    skipped.push(`${rel}:${m.line} ${name} :: ${m.message.slice(0, 55)}`);
  }

  if (changed) fs.writeFileSync(f.filePath, lines.join("\n"));
}

console.log("FIXED:", fixed);
console.log("\n--- skipped (manual) ---");
console.log(skipped.join("\n"));
