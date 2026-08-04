/** Generates a standalone HTML report comparing backtested strategies. */

export interface CompareResult {
  strategy: string;
  run_id: string;
  status: string;
  error?: string;
  metrics?: {
    total_return_pct?: number;
    sharpe_ratio?: number;
    win_rate?: number;
    max_drawdown_pct?: number;
    total_trades?: number;
    annualized_return_pct?: number;
  };
}

interface ReportParams {
  /** The symbol used in the snapshot (e.g. "فولاد") */
  snapshotSymbol: string;
  /** The symbol displayed in the report header */
  displaySymbol: string;
  /** All strategy results */
  results: CompareResult[];
  /** Best strategy name (or null) */
  best: string | null;
  /** Worst strategy name (or null) */
  worst: string | null;
}

export function generateCompareReportHtml({
  snapshotSymbol,
  displaySymbol,
  results,
  best: compareBest,
  worst: compareWorst,
}: ReportParams): string {
  const reportSymbol = snapshotSymbol;
  const compareSymbol = displaySymbol;
  const completed = results.filter(r => r.status !== "failed" && r.metrics?.total_return_pct != null);
  const failed = results.filter(r => r.status === "failed");
  const sortedByReturn = [...completed].sort((a, b) => (b.metrics?.total_return_pct ?? 0) - (a.metrics?.total_return_pct ?? 0));
  const hasCompleted = sortedByReturn.length > 0;

  const barMax = hasCompleted ? Math.max(...sortedByReturn.map(r => Math.abs(r.metrics?.total_return_pct ?? 0)), 1) : 1;
  const barChartBars = sortedByReturn.map((r, i) => {
    const val = r.metrics?.total_return_pct ?? 0;
    const pct = Math.abs(val) / barMax * 100;
    const color = val >= 0 ? "#22c55e" : "#ef4444";
    const isBest = r.strategy === compareBest;
    const isWorst = r.strategy === compareWorst;
    const bg = isBest ? "rgba(34,197,94,0.08)" : isWorst ? "rgba(239,68,68,0.08)" : i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent";
    return `
        <tr style="background:${bg}">
          <td style="padding:8px 12px;font-weight:${isBest||isWorst?'700':'400'};color:${isBest?'#22c55e':isWorst?'#ef4444':'#e2e8f0'}">
            ${isBest ? '🏆 ' : isWorst ? '🫤 ' : ''}${r.strategy}
          </td>
          <td style="padding:8px 12px;text-align:right;direction:ltr">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;height:20px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:${color};border-radius:4px;transition:width 0.5s"></div>
              </div>
              <span style="font-family:monospace;color:${color};font-weight:700;min-width:70px;text-align:right">${val >= 0 ? '+' : ''}${val.toFixed(1)}%</span>
            </div>
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:${(r.metrics?.sharpe_ratio ?? 0) >= 1 ? '#22c55e' : (r.metrics?.sharpe_ratio ?? 0) >= 0 ? '#eab308' : '#ef4444'};text-align:center">
            ${(r.metrics?.sharpe_ratio ?? 0).toFixed(2)}
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:${(r.metrics?.win_rate ?? 0) >= 50 ? '#22c55e' : '#ef4444'};text-align:center">
            ${(r.metrics?.win_rate ?? 0).toFixed(1)}%
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:#94a3b8;text-align:center">
            ${(r.metrics?.max_drawdown_pct ?? 0).toFixed(1)}%
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:#94a3b8;text-align:center">
            ${r.metrics?.total_trades ?? 0}
          </td>
        </tr>`;
  }).join("\n");

  const failedRows = failed.map(r => `
      <tr style="opacity:0.5">
        <td style="padding:8px 12px;color:#94a3b8">${r.strategy}</td>
        <td colspan="5" style="padding:8px 12px;color:#ef4444;text-align:center">❌ ${r.error || "ناموفق"}</td>
      </tr>`
  ).join("\n");

  const now = new Date();
  const dateStr = now.toLocaleDateString("fa-IR", { year: "numeric", month: "long", day: "numeric" });

  return `<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>📊 گزارش مقایسه استراتژی‌ها — ${reportSymbol}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;900&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Vazirmatn',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:40px;line-height:1.6}
  @media print{body{padding:20px;background:#fff;color:#1e293b}.card,.table-wrap{background:#fff!important;border-color:#e2e8f0!important;box-shadow:none!important}th{color:#64748b!important}td{color:#1e293b!important}.badge{background:#f1f5f9!important;color:#1e293b!important}.metric{color:#1e293b!important}h1,h2{color:#0f172a!important}.bar-bg{background:#f1f5f9!important}.header-row{background:#f8fafc!important}.no-print{display:none!important}}
  h1{font-size:24px;font-weight:900;margin-bottom:4px;background:linear-gradient(135deg,#818cf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .subtitle{color:#64748b;font-size:13px;margin-bottom:24px}
  .header-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;background:rgba(255,255,255,0.03);border-radius:12px;padding:16px 20px;border:1px solid rgba(255,255,255,0.06)}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:28px}
  .card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px;text-align:center}
  .card .label{font-size:11px;color:#64748b;margin-bottom:4px}
  .card .value{font-size:22px;font-weight:700}
  .card .value.green{color:#22c55e}.card .value.red{color:#ef4444}.card .value.amber{color:#eab308}
  .table-wrap{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;overflow:hidden;margin-bottom:28px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{padding:10px 12px;text-align:center;color:#64748b;font-weight:700;font-size:11px;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,0.06)}
  th:first-child{text-align:right}
  td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.03)}
  .best-badge{display:inline-block;background:rgba(34,197,94,0.15);color:#22c55e;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700}
  .worst-badge{display:inline-block;background:rgba(239,68,68,0.15);color:#ef4444;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700}
  .footer{text-align:center;color:#475569;font-size:11px;margin-top:32px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.06)}
  @page{size:A4;margin:15mm}
</style>
</head>
<body>
  <div class="header-row">
    <div>
      <h1>📊 گزارش مقایسه استراتژی‌ها</h1>
      <p class="subtitle">نماد: ${compareSymbol} • تاریخ: ${dateStr} • ${completed.length} استراتژی</p>
    </div>
    <div style="display:flex;gap:8px">
      ${compareBest ? "<span class=\"best-badge\">🏆 بهترین: " + compareBest + "</span>" : ''}
      ${compareWorst ? "<span class=\"worst-badge\">🫤 بدترین: " + compareWorst + "</span>" : ''}
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="label">کل استراتژی‌ها</div>
      <div class="value" style="color:#e2e8f0">${results.length}</div>
    </div>
    <div class="card">
      <div class="label">موفق</div>
      <div class="value green">${completed.length}</div>
    </div>
    <div class="card">
      <div class="label">ناموفق</div>
      <div class="value red">${failed.length}</div>
    </div>
    <div class="card">
      <div class="label">بهترین بازده</div>
      <div class="value ${(sortedByReturn[0]?.metrics?.total_return_pct ?? 0) >= 0 ? 'green' : 'red'}">
        ${sortedByReturn.length > 0 ? `${sortedByReturn[0].metrics?.total_return_pct?.toFixed(1)}%` : '—'}
      </div>
    </div>
    <div class="card">
      <div class="label">بدترین بازده</div>
      <div class="value ${(sortedByReturn[sortedByReturn.length-1]?.metrics?.total_return_pct ?? 0) >= 0 ? 'green' : 'red'}">
        ${sortedByReturn.length > 0 ? `${sortedByReturn[sortedByReturn.length-1].metrics?.total_return_pct?.toFixed(1)}%` : '—'}
      </div>
    </div>
    <div class="card">
      <div class="label">میانگین بازده</div>
      <div class="value" style="color:#a78bfa">
        ${completed.length > 0 ? `${(completed.reduce((s,r) => s + (r.metrics?.total_return_pct ?? 0), 0) / completed.length).toFixed(1)}%` : '—'}
      </div>
    </div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="text-align:right">استراتژی</th>
          <th style="text-align:right">بازده کل</th>
          <th>شارپ</th>
          <th>Win Rate</th>
          <th>Max DD</th>
          <th>معاملات</th>
        </tr>
      </thead>
      <tbody>
        ${barChartBars}
        ${failedRows}
      </tbody>
    </table>
  </div>

  ${hasCompleted ? `
  <div style="margin-bottom:28px">
    <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;color:#e2e8f0">📈 نمودار مقایسه بازده کل</h2>
    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:24px;direction:ltr">
      <svg viewBox="0 0 ${Math.max(700, sortedByReturn.length * 80)} ${sortedByReturn.length * 50 + 60}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
        ${sortedByReturn.map((r, i) => {
          const val = r.metrics?.total_return_pct ?? 0;
          const absVal = Math.abs(val);
          const barMaxVal = Math.max(...sortedByReturn.map(x => Math.abs(x.metrics?.total_return_pct ?? 0)), 1);
          const barPct = (absVal / barMaxVal) * 100;
          const barColor = val >= 0 ? "#22c55e" : "#ef4444";
          const y = i * 50 + 10;
          const barHeight = 30;
          const zeroX = 100;
          const maxBarWidth = 520;
          const barWidth = (barPct / 100) * maxBarWidth;
          const isBest = r.strategy === compareBest;
          const isWorst = r.strategy === compareWorst;
          return `
            <g>
              ${isBest ? `<rect x="${zeroX - maxBarWidth - 10}" y="${y - 4}" width="${maxBarWidth + 140}" height="${barHeight + 8}" rx="6" fill="rgba(34,197,94,0.06)"/>` : ''}
              ${isWorst ? `<rect x="${zeroX - maxBarWidth - 10}" y="${y - 4}" width="${maxBarWidth + 140}" height="${barHeight + 8}" rx="6" fill="rgba(239,68,68,0.06)"/>` : ''}
              <text x="${Math.min(zeroX - 4, zeroX - 8)}" y="${y + barHeight / 2 + 4}" text-anchor="end" fill="#94a3b8" font-size="11" font-family="Vazirmatn">${r.strategy}</text>
              ${val >= 0
                ? `<rect x="${zeroX}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="${barColor}" opacity="0.85"/>
                   <text x="${zeroX + barWidth + 6}" y="${y + barHeight / 2 + 4}" fill="${barColor}" font-size="11" font-family="monospace" font-weight="700">+${val.toFixed(1)}%</text>`
                : `<rect x="${zeroX - barWidth}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="${barColor}" opacity="0.85"/>
                   <text x="${zeroX - barWidth - 6}" y="${y + barHeight / 2 + 4}" text-anchor="end" fill="${barColor}" font-size="11" font-family="monospace" font-weight="700">${val.toFixed(1)}%</text>`
              }
              ${i === 0 ? `<line x1="${zeroX}" y1="0" x2="${zeroX}" y2="${sortedByReturn.length * 50}" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
                          <text x="${zeroX}" y="-6" text-anchor="middle" fill="#64748b" font-size="10">صفر</text>` : ''}
            </g>`;
        }).join("\n")}
      </svg>
    </div>
  </div>
  ` : `<p style="text-align:center;color:#64748b;padding:24px">هیچ استراتژی موفقی برای نمایش نمودار وجود ندارد</p>`}

  <div class="footer">
    <p>تولید شده توسط سامانه تحلیل بازار • ${dateStr}</p>
    <p style="margin-top:4px;font-size:10px;color:#334155">این گزارش به صورت خودکار از نتایج مقایسه استراتژی‌ها تولید شده است</p>
  </div>

  <div class="no-print" style="text-align:center;margin-top:24px">
    <button onclick="window.print()" style="background:#818cf8;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;font-family:Vazirmatn">
      🖨️ ذخیره به صورت PDF (چاپ)
    </button>
  </div>
</body>
</html>`;
}
