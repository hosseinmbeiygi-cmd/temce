"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface TableInfo {
  name: string;
  row_count: number;
}

interface ColumnInfo {
  name: string;
  type: string;
}

interface TableData {
  table: string;
  columns: ColumnInfo[];
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface SearchResult {
  table: string;
  total: number;
  columns: ColumnInfo[];
  rows: Record<string, unknown>[];
}

const SEARCHABLE = [
  "instruments", "quotes", "trades", "signals", "recommendations",
  "indicators", "news_articles", "codal_reports", "alerts",
  "backtest_trades", "portfolio_positions", "orderbooks",
];

function extract(resp: unknown) {
  if (resp && typeof resp === "object" && "data" in resp)
    return (resp as { data?: Record<string, unknown> }).data ?? null;
  return null;
}

// ------ Sidebar ------------------------------------------------------------------------------------------------------------------------------

function TableList({
  tables, selected, onSelect, isLoading,
}: {
  tables: TableInfo[]; selected: string | null;
  onSelect: (n: string) => void; isLoading: boolean;
}) {
  const [f, setF] = useState("");
  if (isLoading) return <div className="space-y-1">{[1,2,3,4,5,6,7,8].map(i => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}</div>;
  const list = f ? tables.filter(t => t.name.includes(f)) : tables;
  return (
    <div>
      <input type="text" value={f} onChange={e => setF(e.target.value)} placeholder="فیلتر جدول..."
        style={{ fontWeight: 700, fontSize: 14, color: "#e2e8f0" }}
        className="w-full px-3 py-2.5 bg-surface-800 border border-surface-700 rounded-lg focus:outline-none focus:border-primary-500 mb-3" />
      <div className="space-y-1 max-h-[calc(100vh-320px)] overflow-y-auto">
        {list.map(t => (
          <button key={t.name} onClick={() => onSelect(t.name)}
            style={{ fontWeight: 700, fontSize: 14, color: selected === t.name ? "#a5b4fc" : "#e2e8f0",
              background: selected === t.name ? "rgba(79,70,229,0.15)" : "transparent",
              border: selected === t.name ? "1px solid rgba(99,102,241,0.3)" : "1px solid transparent" }}
            className="w-full text-right px-3 py-2.5 rounded-lg transition-colors flex items-center justify-between hover:bg-surface-800">
            <span style={{ fontFamily: "monospace" }}>{t.name}</span>
            <span style={{ fontSize: 12, color: "#94a3b8", fontFamily: "monospace" }}>
              {t.row_count >= 0 ? t.row_count.toLocaleString() : "?"}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ------ Data table ---------------------------------------------------------------------------------------------------------------------

function DataTable({ data }: { data: TableData }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data: resp, isLoading } = useQuery({
    queryKey: ["table-data", data.table, page, search],
    queryFn: async () => {
      const p = new URLSearchParams({ page: String(page), page_size: "50" });
      if (search) p.set("search", search);
      return apiGet<unknown>(`/tables/${data.table}?${p}`);
    },
  });

  const d = resp ? extract(resp) as TableData | null : null;
  const dis = d || data;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, gap: 16 }}>
        <input type="text" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
          placeholder="جستجو در این جدول..."
          style={{ fontWeight: 700, fontSize: 14, color: "#e2e8f0", padding: "8px 16px", background: "#1e293b", border: "1px solid #334155", borderRadius: 8, width: 224, outline: "none" }} />
        <div style={{ fontWeight: 700, fontSize: 13, color: "#94a3b8", fontFamily: "monospace" }} dir="ltr">
          {dis.total.toLocaleString()} rows | Page {dis.page}/{dis.total_pages}
        </div>
      </div>
      <div style={{ overflowX: "auto", borderRadius: 12, border: "1px solid rgba(51,65,85,0.5)" }}>
        <table style={{ width: "100%", textAlign: "right", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "rgba(30,41,59,0.8)", borderBottom: "1px solid #334155" }}>
              <th style={{ padding: "12px 12px", fontWeight: 700, fontSize: 14, color: "#cbd5e1", width: 40 }}>#</th>
              {dis.columns.map(col => (
                <th key={col.name} style={{ padding: "12px 12px", fontWeight: 700, fontSize: 14, color: "#cbd5e1", whiteSpace: "nowrap", textAlign: "right" }}>
                  <div>{col.name}</div>
                  <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace" }}>{col.type}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={dis.columns.length + 1} style={{ padding: 40, textAlign: "center", color: "#94a3b8", fontWeight: 700 }}>در حال بارگذاری...</td></tr>
            ) : dis.rows.length === 0 ? (
              <tr><td colSpan={dis.columns.length + 1} style={{ padding: 40, textAlign: "center", color: "#94a3b8", fontWeight: 700 }}>داده‌ای یافت نشد</td></tr>
            ) : (
              dis.rows.map((row, i) => (
                <tr key={i} style={{ borderBottom: "1px solid rgba(30,41,59,0.5)" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 700, fontSize: 13, color: "#64748b", fontFamily: "monospace" }}>
                    {(dis.page - 1) * dis.page_size + i + 1}
                  </td>
                  {dis.columns.map(col => {
                    const val = row[col.name];
                    const sv = val == null ? "—" : typeof val === "object" ? JSON.stringify(val) : String(val);
                    return (
                      <td key={col.name} style={{ padding: "10px 12px", fontWeight: 700, fontSize: 13, color: "#f1f5f9", fontFamily: "monospace", maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                        title={sv.length > 60 ? sv : undefined}>
                        {sv.length > 60 ? sv.slice(0, 60) + "..." : sv}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {dis.total_pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            style={{ padding: "8px 16px", borderRadius: 8, background: "#1e293b", color: "#e2e8f0", fontWeight: 700, fontSize: 14, opacity: page <= 1 ? 0.4 : 1, cursor: "pointer", border: "none" }}>قبلی</button>
          {Array.from({ length: Math.min(7, dis.total_pages) }, (_, i) => {
            const s = Math.max(1, Math.min(page - 3, dis.total_pages - 6));
            const p = s + i;
            if (p > dis.total_pages) return null;
            return (
              <button key={p} onClick={() => setPage(p)}
                style={{ padding: "8px 16px", borderRadius: 8, fontWeight: 700, fontSize: 14, cursor: "pointer", border: "none",
                  background: p === page ? "#4f46e5" : "#1e293b", color: "#fff" }}>{p}</button>
            );
          })}
          <button onClick={() => setPage(p => Math.min(dis.total_pages, p + 1))} disabled={page >= dis.total_pages}
            style={{ padding: "8px 16px", borderRadius: 8, background: "#1e293b", color: "#e2e8f0", fontWeight: 700, fontSize: 14, opacity: page >= dis.total_pages ? 0.4 : 1, cursor: "pointer", border: "none" }}>بعدی</button>
        </div>
      )}
    </div>
  );
}

// ------ Global search ------------------------------------------------------------------------------------------------------------

function GlobalSearch({ query }: { query: string }) {
  const [open, setOpen] = useState<string | null>(null);

  const { data: resp, isLoading } = useQuery({
    queryKey: ["global-search", query],
    queryFn: async () => {
      const ps = SEARCHABLE.map(async (tn) => {
        try {
          const r = await apiGet<unknown>(`/tables/${tn}?page=1&page_size=20&search=${encodeURIComponent(query)}`);
          const d = extract(r);
          if (d && typeof d === "object" && "rows" in d && Array.isArray(d.rows) && d.rows.length > 0)
            return { table: tn, total: d.total as number, columns: d.columns as ColumnInfo[], rows: d.rows as Record<string, unknown>[] } as SearchResult;
        } catch {}
        return null;
      });
      return (await Promise.all(ps)).filter(Boolean) as SearchResult[];
    },
  });

  const results = resp || [];

  if (isLoading) return (
    <div className="space-y-4">
      {[1,2,3].map(i => <div key={i} className="glass-card p-4"><Skeleton className="h-7 w-36 mb-3" />{[1,2,3].map(j => <Skeleton key={j} className="h-9 w-full mb-1" />)}</div>)}
    </div>
  );

  if (results.length === 0) return (
    <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>
      <span className="material-icons" style={{ fontSize: 56, display: "block", marginBottom: 16 }}>search_off</span>
      <div style={{ fontWeight: 700, fontSize: 18 }}>نتیجه‌ای برای &quot;{query}&quot; یافت نشد</div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div style={{ fontWeight: 700, fontSize: 14, color: "#cbd5e1", marginBottom: 8 }}>
        {results.length} جدول — {results.reduce((s, r) => s + r.total, 0).toLocaleString()} ردیف یافت شد
      </div>
      {results.map(r => {
        const isOn = open === r.table;
        return (
          <div key={r.table} className="glass-card overflow-hidden">
            <button onClick={() => setOpen(isOn ? null : r.table)}
              style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", padding: 16, background: "transparent", border: "none", cursor: "pointer", color: "#e2e8f0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="material-icons" style={{ color: "#818cf8" }}>table_chart</span>
                <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 16, color: "#f1f5f9" }}>{r.table}</span>
                <span style={{ fontSize: 12, background: "rgba(79,70,229,0.15)", color: "#a5b4fc", padding: "4px 10px", borderRadius: 99, fontWeight: 700 }}>
                  {r.total.toLocaleString()} ردیف
                </span>
              </div>
              <span className="material-icons" style={{ color: "#94a3b8", fontSize: 20 }}>{isOn ? "expand_less" : "expand_more"}</span>
            </button>
            {isOn && (
              <div style={{ borderTop: "1px solid rgba(51,65,85,0.5)", padding: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", textAlign: "right", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #334155" }}>
                      {r.columns.map(col => (
                        <th key={col.name} style={{ padding: "8px 12px", fontWeight: 700, fontSize: 14, color: "#cbd5e1", whiteSpace: "nowrap", textAlign: "right" }}>{col.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {r.rows.map((row, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid rgba(30,41,59,0.3)" }}>
                        {r.columns.map(col => {
                          const val = row[col.name];
                          const sv = val == null ? "—" : typeof val === "object" ? JSON.stringify(val) : String(val);
                          return (
                            <td key={col.name} style={{ padding: "8px 12px", fontWeight: 700, fontSize: 13, color: "#f1f5f9", fontFamily: "monospace", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={sv}>
                              {sv.length > 45 ? sv.slice(0, 45) + "..." : sv}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {r.total > 20 && (
                  <div style={{ textAlign: "center", fontSize: 12, color: "#94a3b8", marginTop: 12, fontWeight: 700 }}>
                    نمایش ۲۰ از {r.total.toLocaleString()} ردیف
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ------ Main page ------------------------------------------------------------------------------------------------------------------------

export default function TablesPage() {
  const [sel, setSel] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [activeQ, setActiveQ] = useState("");

  const { data: tResp, isLoading, error: tErr } = useQuery({
    queryKey: ["tables-list"],
    queryFn: async () => apiGet<unknown>("/tables"),
  });

  const tables: TableInfo[] =
    (tResp && typeof tResp === "object" && "data" in tResp)
      ? ((tResp as { data?: { tables?: TableInfo[] } }).data?.tables ?? []) : [];

  const { data: dResp, isLoading: loadingData } = useQuery({
    queryKey: ["table-data", sel],
    queryFn: async () => apiGet<unknown>(`/tables/${sel}?page=1&page_size=50`),
    enabled: !!sel,
  });

  const tableData: TableData | null =
    (dResp && typeof dResp === "object" && "data" in dResp)
      ? (dResp as { data?: TableData }).data ?? null : null;

  const showSearch = activeQ.length > 0;
  const showTable = sel && !showSearch;

  function doSearch(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim()) { setActiveQ(q.trim()); setSel(null); }
  }

  function clear() { setActiveQ(""); setQ(""); }

  return (
    <AppLayout title="مرور جداول دیتابیس" subtitle="جستجوی نماد در تمام جداول پایگاه داده">
      {/* Search bar */}
      <div className="glass-card" style={{ padding: 20, marginBottom: 24 }}>
        <form onSubmit={doSearch} style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="material-icons" style={{ color: "#94a3b8", fontSize: 24 }}>search</span>
          <input type="text" value={q} onChange={e => setQ(e.target.value)}
            placeholder="نام نماد را تایپ کنید (مثال: فولاد، شپنا، وبملت)"
            style={{ flex: 1, padding: "12px 20px", background: "#1e293b", border: "1px solid #334155", borderRadius: 12,
              fontWeight: 700, fontSize: 16, color: "#f1f5f9", outline: "none" }} />
          <button type="submit"
            style={{ padding: "12px 24px", background: "#4f46e5", color: "#fff", borderRadius: 12,
              fontWeight: 700, fontSize: 16, border: "none", cursor: "pointer" }}>جستجو</button>
          {activeQ && (
            <button type="button" onClick={clear}
              style={{ padding: "12px 20px", background: "#334155", color: "#e2e8f0", borderRadius: 12,
                fontWeight: 700, fontSize: 14, border: "none", cursor: "pointer" }}>پاک کردن</button>
          )}
        </form>
        {activeQ && (
          <div style={{ marginTop: 12, fontWeight: 700, fontSize: 14, color: "#cbd5e1" }}>
            جستجوی: <span style={{ fontFamily: "monospace", color: "#a5b4fc", fontSize: 16 }}>{activeQ}</span>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 24 }}>
        {/* Sidebar */}
        <div style={{ width: 288, flexShrink: 0 }}>
          <div className="glass-card" style={{ padding: 16 }}>
            <h3 style={{ fontWeight: 700, fontSize: 16, color: "#f1f5f9", marginBottom: 12 }}>
              جداول ({tables.length})
            </h3>
            {tErr ? (
              <div style={{ fontSize: 14, color: "#f43f5e", background: "rgba(244,63,94,0.1)", padding: 16, borderRadius: 8, fontWeight: 700 }}>
                <div style={{ marginBottom: 4 }}>خطا در اتصال به سرور</div>
                <div style={{ color: "#94a3b8", fontFamily: "monospace", fontSize: 12 }}>
                  {tErr instanceof Error ? tErr.message : "خطای ناشناخته"}
                </div>
              </div>
            ) : (
              <TableList tables={tables} selected={sel} onSelect={n => { setSel(n); clear(); }} isLoading={isLoading} />
            )}
          </div>
        </div>

        {/* Main */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="glass-card" style={{ padding: 20 }}>
            {showSearch ? <GlobalSearch query={activeQ} />
            : showTable ? (
              loadingData && !tableData ? (
                <div className="space-y-3">
                  <Skeleton className="h-10 w-52" />
                  {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-11 w-full" />)}
                </div>
              ) : tableData ? <DataTable data={tableData} /> : null
            ) : (
              <div style={{ textAlign: "center", padding: 80, color: "#94a3b8" }}>
                <span className="material-icons" style={{ fontSize: 64, display: "block", marginBottom: 16 }}>table_chart</span>
                <div style={{ fontWeight: 700, fontSize: 18 }}>نام نماد را در بالا جستجو کنید</div>
                <div style={{ fontSize: 14, color: "#64748b", marginTop: 8, fontWeight: 700 }}>یا یک جدول را از لیست سمت راست انتخاب کنید</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
