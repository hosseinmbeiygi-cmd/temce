"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import Skeleton from "@/components/Skeleton";

// ── Types ───────────────────────────────────────────────────────────

interface TableStatus {
  table_name: string;
  row_count: number;
  last_updated: string | null;
  status: "ok" | "missing";
  error?: string;
}

interface ArchitectureInfo {
  version: string;
  title: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface MigrationStatusData {
  alembic_revision: string | null;
  tables: TableStatus[];
  architecture: ArchitectureInfo | null;
  total_decision_engine_tables: number;
  migration_applied: boolean;
}

interface ApiMigrationResponse {
  success: boolean;
  data: MigrationStatusData;
}

// ── Helpers ─────────────────────────────────────────────────────────

function tableLabel(name: string): string {
  switch (name) {
    case "decision_architectures": return "decision_architectures (معماری)";
    case "decision_results": return "decision_results (تصمیمات)";
    case "alembic_version": return "alembic_version (مهاجرت)";
    default: return name;
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("fa-IR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ── Component ───────────────────────────────────────────────────────

export default function MigrationStatusPanel() {
  const { data, isLoading, isError, refetch } = useQuery<ApiMigrationResponse>({
    queryKey: ["dss-migration-status"],
    queryFn: () => apiGet<ApiMigrationResponse>("/decision-engine/migration-status"),
    staleTime: 30_000,
    refetchInterval: 120_000,
  });

  const status = data?.data;

  if (isLoading) {
    return (
      <div className="glass-card p-4">
        <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
          <span className="material-icons text-sm">database_check</span>
          وضعیت migration و جداول
        </h2>
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }

  if (isError || !status) {
    return (
      <div className="glass-card p-4">
        <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
          <span className="material-icons text-sm">database_check</span>
          وضعیت migration و جداول
        </h2>
        <div className="py-4 text-center">
          <span className="material-icons text-xl text-accent-rose mb-1">cloud_off</span>
          <p className="text-[10px] text-surface-500">سرور در دسترس نیست</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-[9px] px-3 py-1.5 bg-surface-800 rounded-lg text-surface-400 hover:text-surface-200 transition-all"
          >
            تلاش مجدد
          </button>
        </div>
      </div>
    );
  }

  const migrationOk = status.migration_applied;
  const archDecks = status.tables.find((t) => t.table_name === "decision_architectures");
  const decResults = status.tables.find((t) => t.table_name === "decision_results");

  return (
    <div className="glass-card p-4">
      <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
        <span className="material-icons text-sm">database_check</span>
        وضعیت migration و جداول
      </h2>

      {/* ── Migration status badge ── */}
      <div className="flex items-center justify-between mb-3 p-3 rounded-xl border"
        style={{
          borderColor: migrationOk ? "#10b98130" : "#ef444430",
          backgroundColor: migrationOk ? "#10b98108" : "#ef444408",
        }}
      >
        <div>
          <div className="text-[11px] font-bold text-surface-200 flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${migrationOk ? "bg-accent-emerald" : "bg-accent-rose"}`} />
            {migrationOk ? "Migration اعمال شده" : "Migration انجام نشده"}
          </div>
          {status.alembic_revision && (
            <div className="text-[9px] text-surface-500 mt-1 font-mono">
              آخرین revision: {status.alembic_revision}
            </div>
          )}
        </div>
        <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-1 rounded-lg">
          {status.total_decision_engine_tables} جدول
        </span>
      </div>

      {/* ── Table status cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
        {status.tables.map((tbl) => (
          <div
            key={tbl.table_name}
            className="rounded-xl p-3 border transition-all"
            style={{
              borderColor: tbl.status === "ok" ? "#10b98120" : "#ef444420",
              backgroundColor: tbl.status === "ok" ? "#10b98105" : "#ef444405",
            }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-medium text-surface-400">{tableLabel(tbl.table_name)}</span>
              <span className={`w-1.5 h-1.5 rounded-full ${tbl.status === "ok" ? "bg-accent-emerald" : "bg-accent-rose"}`} />
            </div>
            <div className="text-lg font-black text-surface-200 font-mono">
              {tbl.row_count.toLocaleString()}
            </div>
            <div className="text-[8px] text-surface-500 mt-0.5">
              {tbl.status === "ok"
                ? `آخرین به‌روزرسانی: ${formatDate(tbl.last_updated)}`
                : tbl.error || "جدول وجود ندارد"}
            </div>
          </div>
        ))}
      </div>

      {/* ── Architecture version info ── */}
      {status.architecture && (
        <div className="rounded-xl p-3 border border-primary-600/20 bg-primary-600/05">
          <div className="text-[9px] font-medium text-surface-500 mb-1">معماری فعال</div>
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[11px] font-bold text-primary-300">{status.architecture.title}</span>
              <span className="text-[9px] text-surface-500 mr-2 font-mono">v{status.architecture.version}</span>
            </div>
            <div className="text-[8px] text-surface-500 text-left">
              <div>ایجاد: {formatDate(status.architecture.created_at)}</div>
              {status.architecture.updated_at && (
                <div>ویرایش: {formatDate(status.architecture.updated_at)}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Actions ── */}
      <div className="flex justify-end mt-3 pt-3 border-t border-surface-800/30">
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[9px] font-medium text-surface-500 hover:text-surface-300 bg-surface-800/50 hover:bg-surface-800 transition-all"
        >
          <span className="material-icons text-xs">refresh</span>
          به‌روزرسانی
        </button>
      </div>
    </div>
  );
}
