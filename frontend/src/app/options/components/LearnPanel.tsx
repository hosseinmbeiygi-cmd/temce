"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { GlossaryItem, MistakeItem } from "./types";

interface ExampleItem {
  strategy?: string;
  symbol?: string;
  [key: string]: unknown;
}

interface SyllabusItem {
  section?: number;
  title?: string;
  topics?: string[];
}

export default function LearnPanel() {
  const [tab, setTab] = useState<"glossary" | "mistakes" | "formulas" | "examples" | "syllabus">("glossary");

  const { data: glossaryResp } = useQuery({
    queryKey: ["options", "glossary"],
    queryFn: () => apiGet<{ success: boolean; data: GlossaryItem[] }>("/options/reference/glossary"),
    staleTime: 600_000,
  });

  const { data: mistakesResp } = useQuery({
    queryKey: ["options", "mistakes"],
    queryFn: () => apiGet<{ success: boolean; data: MistakeItem[] }>("/options/reference/mistakes"),
    staleTime: 600_000,
  });

  const { data: formulasResp } = useQuery({
    queryKey: ["options", "formulas"],
    queryFn: () => apiGet<{ success: boolean; data: Record<string, string> }>("/options/reference/formulas"),
    staleTime: 600_000,
  });

  const { data: examplesResp } = useQuery({
    queryKey: ["options", "examples"],
    queryFn: () => apiGet<{ success: boolean; data: ExampleItem[] }>("/options/reference/examples"),
    staleTime: 600_000,
  });

  const { data: syllabusResp } = useQuery({
    queryKey: ["options", "syllabus"],
    queryFn: () => apiGet<{ success: boolean; data: SyllabusItem[] }>("/options/reference/syllabus"),
    staleTime: 600_000,
  });

  const glossary = glossaryResp?.data ?? [];
  const mistakes = mistakesResp?.data ?? [];
  const formulasMap = formulasResp?.data ?? {};
  const examples = examplesResp?.data ?? [];
  const syllabus = syllabusResp?.data ?? [];

  const tabs = [
    { id: "glossary" as const, label: "📚 اصطلاحات" },
    { id: "mistakes" as const, label: "❌ اشتباهات رایج" },
    { id: "formulas" as const, label: "📐 فرمول‌ها" },
    { id: "examples" as const, label: "💼 مصادیق واقعی" },
    { id: "syllabus" as const, label: "🗂 سرفصل دوره" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`flex-1 min-w-fit px-3 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${tab === t.id ? "bg-primary-600/30 text-primary-300" : "text-surface-400 hover:text-surface-200"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "glossary" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {glossary.map((g, i) => (
            <div key={i} className="glass-card p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-surface-200">{g.fa}</span>
                <span className="text-[10px] text-primary-400">{g.en}</span>
              </div>
              <p className="text-[10px] text-surface-500">{g.desc}</p>
            </div>
          ))}
          {glossary.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center col-span-2">اطلاعاتی موجود نیست</p>
          )}
        </div>
      )}

      {tab === "mistakes" && (
        <div className="space-y-2">
          {mistakes.map((m, i) => (
            <div key={i} className="glass-card p-3">
              <div className="flex items-start gap-2">
                <span className="text-accent-rose text-sm">✖</span>
                <div>
                  <p className="text-xs font-bold text-surface-200">{m.mistake}</p>
                  <p className="text-[10px] text-accent-emerald mt-1">✔ {m.solution}</p>
                </div>
              </div>
            </div>
          ))}
          {mistakes.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center">اطلاعاتی موجود نیست</p>
          )}
        </div>
      )}

      {tab === "formulas" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {Object.entries(formulasMap).map(([key, val]) => (
            <div key={key} className="glass-card p-3">
              <p className="text-[10px] text-primary-400 mb-1">{key}</p>
              <p className="text-xs font-mono text-surface-200" dir="ltr">{val}</p>
            </div>
          ))}
          {Object.keys(formulasMap).length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center col-span-2">اطلاعاتی موجود نیست</p>
          )}
        </div>
      )}

      {tab === "examples" && (
        <div className="space-y-2">
          {examples.map((ex, i) => (
            <div key={i} className="glass-card p-3">
              <p className="text-xs font-bold text-surface-200 mb-1">{String(ex.title ?? ex.strategy ?? "مثال")}</p>
              <div className="text-[10px] text-surface-400 space-y-1">
                {Object.entries(ex)
                  .filter(([k]) => k !== "title" && k !== "strategy")
                  .map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <span className="text-surface-500 min-w-fit">{k}:</span>
                      <span>{String(v)}</span>
                    </div>
                  ))}
              </div>
            </div>
          ))}
          {examples.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center">اطلاعاتی موجود نیست</p>
          )}
        </div>
      )}

      {tab === "syllabus" && (
        <div className="space-y-3">
          {syllabus.map((item, i) => (
            <div key={i} className="glass-card p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-bold text-surface-200">{item.title ?? "فصل"}</p>
                {item.section != null && (
                  <span className="text-[10px] text-surface-500">فصل {item.section}</span>
                )}
              </div>
              {Array.isArray(item.topics) && item.topics.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.topics.map((t, j) => (
                    <span key={j} className="px-2 py-0.5 bg-surface-800/50 rounded text-[10px] text-surface-400">{t}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
          {syllabus.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center">اطلاعاتی موجود نیست</p>
          )}
        </div>
      )}
    </div>
  );
}
