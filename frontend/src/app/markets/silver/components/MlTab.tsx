"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
import { fa, faDateTime, isSilverText, metricEntries } from "./helpers";

interface MlModelVersion {
  version: string;
  stage: string;
  metrics: Record<string, unknown>;
  parameters: Record<string, unknown>;
  artifact_path: string;
  created_at: string | null;
}

interface MlModel {
  id: string;
  name: string;
  task: string;
  framework: string;
  model_type: string;
  latest_version: string;
  description: string;
  tags: string[];
  versions: MlModelVersion[];
  created_at: string | null;
}

interface MlRun {
  id: string;
  experiment_name: string;
  run_name: string;
  model_type: string;
  symbol: string | null;
  symbols: string[];
  status: string;
  metrics: Record<string, unknown>;
  best_params: Record<string, unknown>;
  progress_pct: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

const stageTone: Record<string, string> = {
  production: "border-up/30 bg-up/10 text-up",
  staging: "border-warn/30 bg-warn/10 text-warn",
  development: "border-line bg-soft text-ink-3",
};

const statusTone: Record<string, string> = {
  completed: "text-up",
  running: "text-warn",
  failed: "text-down",
  pending: "text-ink-3",
};

export default function MlTab() {
  const [query, setQuery] = useState("");

  const modelsQ = useQuery({
    queryKey: ["silver-ml-models"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data?: MlModel[] }>("/ml/models");
      return extractArray<MlModel>(r?.data ?? r);
    },
    staleTime: 300_000,
  });

  const runsQ = useQuery({
    queryKey: ["silver-ml-runs"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data?: MlRun[] }>("/ml/runs");
      return extractArray<MlRun>(r?.data ?? r);
    },
    staleTime: 120_000,
  });

  const q = query.trim().toLowerCase();

  const models = useMemo(() => {
    const list = modelsQ.data ?? [];
    const silver = list.filter((m) => isSilverText(`${m.name} ${m.tags?.join(" ")}`));
    const base = silver.length ? silver : list;
    if (!q) return base;
    return base.filter((m) => `${m.name} ${m.framework} ${m.task} ${m.tags?.join(" ")}`.toLowerCase().includes(q));
  }, [modelsQ.data, q]);

  const runs = useMemo(() => {
    const list = runsQ.data ?? [];
    const silver = list.filter((r) => isSilverText(`${r.symbol ?? ""} ${r.symbols?.join(" ")} ${r.run_name}`));
    const base = silver.length ? silver : list;
    if (!q) return base;
    return base.filter((r) => `${r.run_name} ${r.experiment_name} ${r.model_type} ${r.symbol ?? ""}`.toLowerCase().includes(q));
  }, [runsQ.data, q]);

  const loading = modelsQ.isLoading || runsQ.isLoading;

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h3 className="text-sm font-black text-ink">مدل‌های یادگیری ماشین و اجراهای آموزش</h3>
            <p className="mt-1 text-[11px] text-ink-3">
              مدل‌های ثبت‌شده در سرویس ML و تاریخچه آموزش — در صورت نبود مدل مرتبط با نقره، همه مدل‌های موجود نمایش داده می‌شوند.
            </p>
          </div>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجو: نام مدل، نماد، نوع…"
            className="w-full rounded-xl border border-line bg-soft px-3 py-2 text-xs text-ink sm:w-64"
          />
        </div>
      </section>

      {loading && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-2xl bg-soft" />
          ))}
        </div>
      )}

      {!loading && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {models.map((m) => {
              const latest = m.versions && m.versions.length > 0 ? m.versions[m.versions.length - 1] : undefined;
              const metrics = metricEntries(latest?.metrics ?? {}, 4);
              return (
                <div key={m.id} className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-black text-ink">{m.name}</h4>
                      <p className="mt-0.5 text-[10px] text-ink-3">
                        {m.framework} · {m.task} · نسخه {m.latest_version}
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold ${stageTone[latest?.stage ?? "development"] ?? stageTone.development}`}>
                      {latest?.stage ?? "development"}
                    </span>
                  </div>
                  {m.description && <p className="mt-2 line-clamp-2 text-[11px] text-ink-3">{m.description}</p>}
                  {!!m.tags?.length && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.tags.slice(0, 4).map((t) => (
                        <span key={t} className="rounded-full bg-soft px-2 py-0.5 text-[9px] text-ink-3">{t}</span>
                      ))}
                    </div>
                  )}
                  {metrics.length > 0 && (
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      {metrics.map(([k, v]) => (
                        <div key={k} className="rounded-lg bg-soft px-2 py-1.5 text-center">
                          <p className="truncate text-[9px] text-ink-3">{k}</p>
                          <p className="font-mono text-[11px] font-bold text-ink" dir="ltr">{v}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="mt-2 text-[9px] text-ink-3">ثبت: {faDateTime(m.created_at)}</p>
                </div>
              );
            })}
            {!models.length && (
              <p className="col-span-full rounded-2xl border border-line bg-card px-4 py-10 text-center text-xs text-ink-3">
                مدلی در سرویس ML ثبت نشده است.
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
            <h3 className="mb-3 text-sm font-black text-ink">اجراهای آموزش ({fa(runs.length)})</h3>
            {runs.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-right text-ink-3">
                      <th className="p-2">نام اجرا</th>
                      <th className="p-2">نوع مدل</th>
                      <th className="p-2">نماد</th>
                      <th className="p-2">وضعیت</th>
                      <th className="p-2">کلیدی‌ترین متریک</th>
                      <th className="p-2">تاریخ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.slice(0, 40).map((r) => {
                      const metrics = metricEntries(r.metrics, 1);
                      return (
                        <tr key={r.id} className="border-t border-line">
                          <td className="p-2 font-bold text-ink-2">{r.run_name || r.experiment_name || r.id}</td>
                          <td className="p-2 font-mono text-ink-3">{r.model_type || "—"}</td>
                          <td className="p-2 font-mono">{r.symbol ?? "—"}</td>
                          <td className={`p-2 font-bold ${statusTone[r.status] ?? "text-ink-3"}`}>{r.status}</td>
                          <td className="p-2 font-mono text-ink-2" dir="ltr">{metrics[0] ? `${metrics[0][0]}=${metrics[0][1]}` : "—"}</td>
                          <td className="p-2 text-ink-3">{faDateTime(r.finished_at ?? r.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-6 text-center text-xs text-ink-3">اجرای آموزشی ثبت نشده است.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
