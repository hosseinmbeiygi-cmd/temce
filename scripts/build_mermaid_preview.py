"""Build a self-contained offline preview of every Mermaid diagram in docs/.

Reads all ```mermaid blocks from docs/*.md, inlines the local Mermaid library
(docs/assets/mermaid.min.js) into the page, and writes a single portable HTML
file (docs/mermaid-preview.html) that works from file:// with no internet.

Usage:
    python scripts/build_mermaid_preview.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = DOCS / "mermaid-preview.html"
LIB = DOCS / "assets" / "mermaid.min.js"

PAGE_JS = r"""
/* ── app logic ───────────────────────────────────────────── */
(function () {
  const statusEl = document.getElementById('render-status');
  const searchEl = document.getElementById('search');
  const cards = Array.from(document.querySelectorAll('section.diagram-card'));

  function updateStatus() {
    const svgs = document.querySelectorAll('pre.mermaid svg').length;
    const errors = document.querySelectorAll('pre.mermaid .error-text, pre.mermaid-text').length;
    statusEl.textContent = svgs + ' از ' + cards.length + ' دیاگرام رندر شد' +
      (errors ? ' — ' + errors + ' خطا' : '');
    document.body.dataset.ready = '1';
  }

  window.addEventListener('load', () => setTimeout(updateStatus, 6000));

  /* search filter */
  searchEl.addEventListener('input', () => {
    const q = searchEl.value.trim().toLowerCase();
    cards.forEach(card => {
      const hay = (card.dataset.search || '').toLowerCase();
      card.style.display = (!q || hay.includes(q)) ? '' : 'none';
    });
  });

  /* copy source */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const code = btn.closest('.diagram-card').querySelector('pre.mermaid').dataset.source || '';
    navigator.clipboard.writeText(code).then(() => {
      btn.textContent = '✓ کپی شد';
      setTimeout(() => (btn.textContent = 'کپی سورس'), 1500);
    });
  });

  /* download svg */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-download]');
    if (!btn) return;
    const card = btn.closest('.diagram-card');
    const svg = card.querySelector('pre.mermaid svg');
    if (!svg) return;
    const blob = new Blob([svg.outerHTML], { type: 'image/svg+xml;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (card.dataset.file || 'diagram') + '.svg';
    a.click();
    URL.revokeObjectURL(a.href);
  });

  /* fullscreen zoom */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-zoom]');
    if (!btn) return;
    const card = btn.closest('.diagram-card');
    const svg = card.querySelector('pre.mermaid svg');
    if (!svg) return;
    const ov = document.getElementById('zoom-overlay');
    const host = ov.querySelector('.zoom-host');
    host.innerHTML = '';
    host.appendChild(svg.cloneNode(true));
    ov.classList.add('open');
  });
  document.getElementById('zoom-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'zoom-overlay' || e.target.closest('.zoom-close')) {
      document.getElementById('zoom-overlay').classList.remove('open');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') document.getElementById('zoom-overlay').classList.remove('open');
  });
})();
"""

CSS = """
:root {
  --bg: #f4f6fa;
  --panel: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --muted: #64748b;
  --accent: #0f766e;
  --accent-2: #1d4ed8;
  --badge: #eef2ff;
  --shadow: 0 1px 3px rgba(15,23,42,.08), 0 8px 24px rgba(15,23,42,.06);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: Tahoma, 'Segoe UI', 'Vazirmatn', sans-serif;
  background: var(--bg);
  color: var(--text);
  direction: rtl;
}
/* ── layout ── */
.wrap { display: flex; min-height: 100vh; }
aside {
  width: 280px;
  flex: 0 0 280px;
  background: var(--panel);
  border-left: 1px solid var(--border);
  padding: 20px 16px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
main { flex: 1; min-width: 0; padding: 24px 28px 60px; }
aside h1 { font-size: 17px; margin: 0 0 4px; color: var(--accent); }
aside .sub { font-size: 12px; color: var(--muted); margin: 0 0 14px; }
#search {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 14px;
  background: var(--bg);
}
#search:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
nav a {
  display: block;
  padding: 7px 10px;
  border-radius: 8px;
  color: var(--text);
  text-decoration: none;
  font-size: 13px;
  border-right: 3px solid transparent;
}
nav a:hover { background: var(--badge); }
nav a .n { color: var(--muted); font-size: 11px; }
nav a:target, nav a.active { border-right-color: var(--accent); background: var(--badge); }
nav .file-label {
  font-size: 11px;
  color: var(--muted);
  margin: 14px 6px 4px;
  text-transform: none;
  letter-spacing: 0;
}
/* ── header ── */
.topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; gap: 12px; }
.topbar h2 { margin: 0; font-size: 20px; }
.topbar .count { font-size: 13px; color: var(--muted); }
/* ── cards ── */
section.diagram-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  margin-bottom: 26px;
  overflow: hidden;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.card-head .title { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; }
.badge {
  background: var(--badge);
  color: var(--accent-2);
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  direction: ltr;
  font-family: Consolas, monospace;
}
.kind { font-size: 11px; color: var(--muted); direction: ltr; font-family: Consolas, monospace; }
.actions { display: flex; gap: 6px; }
.actions button {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all .15s;
}
.actions button:hover { background: var(--badge); border-color: var(--accent); color: var(--accent); }
.canvas { padding: 20px; overflow-x: auto; }
pre.mermaid {
  margin: 0;
  text-align: center;
  display: flex;
  justify-content: center;
}
pre.mermaid svg { max-width: 100%; height: auto; }
pre.mermaid-text { display: none; }
/* ── status bar ── */
#render-status {
  position: fixed;
  bottom: 14px;
  left: 14px;
  background: #0f172a;
  color: #fff;
  font-size: 12px;
  padding: 8px 14px;
  border-radius: 999px;
  box-shadow: var(--shadow);
  direction: rtl;
  z-index: 50;
}
#render-status::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  margin-left: 8px;
  vertical-align: middle;
}
body[data-ready='1'] #render-status::before { background: #22c55e; }
/* ── zoom overlay ── */
#zoom-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15,23,42,.88);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 30px;
}
#zoom-overlay.open { display: flex; }
.zoom-host {
  background: #fff;
  border-radius: 14px;
  padding: 24px;
  max-width: 96%;
  max-height: 92%;
  overflow: auto;
  direction: ltr;
  text-align: center;
}
.zoom-host svg { max-width: 100%; height: auto; }
.zoom-close {
  position: absolute;
  top: 16px;
  right: 22px;
  background: #fff;
  border: 0;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
}
/* responsive */
@media (max-width: 900px) {
  .wrap { flex-direction: column; }
  aside { position: static; width: 100%; flex: none; height: auto; }
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --panel: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --badge: #1e3a5f;
    --shadow: 0 1px 3px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.3);
  }
  .actions button { background: #0f172a; }
  .zoom-host { background: #1e293b; }
  pre.mermaid { background: transparent; }
}
"""


def collect_diagrams() -> list[dict]:
    items = []
    for path in sorted(DOCS.glob("*.md")):
        src = path.read_text(encoding="utf-8")
        blocks = re.findall(r"```mermaid\n(.*?)```", src, re.S)
        for i, b in enumerate(blocks, 1):
            code = b.strip()
            kind = code.split("\n", 1)[0][:40]
            items.append(
                {
                    "file": path.name,
                    "idx": i,
                    "code": code,
                    "kind": kind,
                }
            )
    return items


def build() -> None:
    if not LIB.exists():
        raise SystemExit(
            f"ERROR: {LIB} not found.\n"
            "Download it first:\n"
            "  curl -L -o docs/assets/mermaid.min.js "
            "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
        )

    items = collect_diagrams()
    lib = LIB.read_text(encoding="utf-8")
    # Prevent the browser from terminating the inline <script> at a literal
    # "</script>" sequence inside the library source.
    lib = lib.replace("</script>", "<\\/script>")

    toc_parts: list[str] = []
    card_parts: list[str] = []
    by_file: dict[str, list[dict]] = {}
    for it in items:
        by_file.setdefault(it["file"], []).append(it)

    current_file = None
    for it in items:
        if it["file"] != current_file:
            current_file = it["file"]
            toc_parts.append(
                f'<div class="file-label">{html.escape(current_file)}</div>'
            )
        toc_parts.append(
            f'<a href="#d-{html.escape(it["file"])}-{it["idx"]}" '
            f'data-file="{html.escape(it["file"])}">'
            f'<span class="n">{it["idx"]}.</span> {it["kind"]}</a>'
        )
        card_id = f'd-{html.escape(it["file"])}-{it["idx"]}'
        card_parts.append(
            "<section class=\"diagram-card\" "
            f'id="{card_id}" '
            f'data-file="{html.escape(it["file"])}" '
            f'data-search="{html.escape(it["file"] + " " + it["kind"])}">'
            '<div class="card-head">'
            '<div class="title">'
            f'<span class="badge">{html.escape(it["file"])} · {it["idx"]}</span>'
            f'<span class="kind">{html.escape(it["kind"])}</span>'
            "</div>"
            '<div class="actions">'
            '<button data-copy>کپی سورس</button>'
            '<button data-download>دانلود SVG</button>'
            '<button data-zoom>تمام‌صفحه</button>'
            "</div>"
            "</div>"
            '<div class="canvas">'
            f'<pre class="mermaid" data-source="{html.escape(it["code"], quote=True)}">{html.escape(it["code"])}</pre>'
            "</div>"
            "</section>"
        )

    page = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>پیش‌نمایش دیاگرام‌های Mermaid — مستندات پروژه</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <aside>
    <h1>📐 دیاگرام‌های مستندات</h1>
    <p class="sub">پیش‌نمایش آفلاین — {len(items)} دیاگرام از {len(by_file)} فایل</p>
    <input id="search" type="search" placeholder="جستجو در دیاگرام‌ها…"/>
    <nav>
{chr(10).join(toc_parts)}
    </nav>
  </aside>
  <main>
    <div class="topbar">
      <h2>همه دیاگرام‌های پروژه</h2>
      <span class="count">{len(items)} دیاگرام · ساخته‌شده از docs/*.md</span>
    </div>
    <div id="diagrams">
{chr(10).join(card_parts)}
    </div>
  </main>
</div>

<div id="zoom-overlay">
  <button class="zoom-close" aria-label="بستن">×</button>
  <div class="zoom-host"></div>
</div>

<div id="render-status">در حال رندر…</div>

<script>{lib}</script>
<script>{PAGE_JS}</script>
</body>
</html>"""

    OUT.write_text(page, encoding="utf-8")
    print(f"OK  {OUT}  ({len(page) / 1024 / 1024:.1f} MB, {len(items)} diagrams)")


if __name__ == "__main__":
    build()
