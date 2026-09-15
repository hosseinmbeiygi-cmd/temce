"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import type { GlossaryItem, MistakeItem } from "./types";

export default function LearnPanel() {
  const [tab, setTab] = useState<"glossary" | "mistakes" | "formulas" | "examples" | "syllabus">("glossary");

  const { data: glossaryResp } = useQuery({
    queryKey: ["options", "glossary"],
    queryFn: () => apiGet<{ success: boolean; data: GlossaryItem[] }>("/api/v1/options/reference/glossary"),
    staleTime: 600_000,
  });

  const { data: mistakesResp } = useQuery({
    queryKey: ["options", "mistakes"],
    queryFn: () => apiGet<{ success: boolean; data: MistakeItem[] }>("/api/v1/options/reference/mistakes"),
    staleTime: 600_000,
  });

  const { data: formulasResp } = useQuery({
    queryKey: ["options", "formulas"],
    queryFn: () => apiGet<{ success: boolean; data: Record<string, string> }>("/api/v1/options/reference/formulas"),
    staleTime: 600_000,
  });

  const { data: examplesResp } = useQuery({
    queryKey: ["options", "examples"],
    queryFn: () => apiGet<{ success: boolean; data: any[] }>("/api/v1/options/reference/examples"),
    staleTime: 600_000,
  });

  const { data: syllabusResp } = useQuery({
    queryKey: ["options", "syllabus"],
    queryFn: () => apiGet<{ success: boolean; data: any[] }>("/api/v1/options/reference/syllabus"),
    staleTime: 600_000,
  });

  const glossary = glossaryResp?.data ?? [];
  const mistakes = mistakesResp?.data ?? [];
  const formulasMap = formulasResp?.data ?? {};
  const examples = examplesResp?.data ?? [];
  const syllabus = syllabusResp?.data ?? [];

  const tabs = [
    { id: "glossary" as const, label: "\u0627\u0635\u0637\u0644\u0627\u062d\u0627\u062a" },
    { id: "mistakes" as const, label: "\u0627\u0634\u062a\u0628\u0627\u0647\u0627\u062a \u0631\u0627\u06cc\u062c" },
    { id: "formulas" as const, label: "\u0641\u0631\u0645\u0648\u0644\u200c\u0647\u0627" },
    { id: "examples" as const, label: "\u0645\u0635\u0627\u062f\u06cc\u0642 \u0648\u0627\u0642\u0639\u06cc" },
    { id: "syllabus" as const, label: "\u0633\u0631\u0641\u0635\u0644 \u062f\u0648\u0631\u0647" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex-1 min-w-fit px-3 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap"
          >
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
            <p className="text-surface-500 text-xs py-4 text-center col-span-2">\u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a</p>
          )}
        </div>
      )}

      {tab === "mistakes" && (
        <div className="space-y-2">
          {mistakes.map((m, i) => (
            <div key={i} className="glass-card p-3">
              <div className="flex items-start gap-2">
                <span className="text-accent-rose text-sm">\u274c</span>
                <div>
                  <p className="text-xs font-bold text-surface-200">{m.mistake}</p>
                  <p className="text-[10px] text-accent-emerald mt-1">\u2714 {m.solution}</p>
                </div>
              </div>
            </div>
          ))}
          {mistakes.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center">\u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a</p>
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
            <p className="text-surface-500 text-xs py-4 text-center col-span-2">\u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a</p>
          )}
        </div>
      )}

      {tab === "examples" && (
        <div className="space-y-2">
          {examples.map((ex, i) => (
            <div key={i} className="glass-card p-3">
              <p className="text-xs font-bold text-surface-200 mb-1">{ex.title || ex.strategy || "\u0645\u062b\u0627\u0644"}</p>
              <div className="text-[10px] text-surface-400 space-y-1">
                {Object.entries(ex).filter(([k]) => k !== "title" && k !== "strategy").map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <span className="text-surface-500 min-w-fit">{k}:</span>
                    <span>{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {examples.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center">\u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a</p>
          )}
        </div>
      )}

      {tab === "syllabus" && (
        <div className="space-y-3">
          {syllabus.map((item: any, i: number) => (
            <div key={i} className="glass-card p-3">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-bold text-surface-200">{item.title || item.chapter || "\u0641\u0635\u0644"}</p>
                {item.duration && (
                  <span className="text-[10px] text-surface-500">{item.duration}</span>
                )}
              </div>
              {item.topics && Array.isArray(item.topics) && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.topics.map((t: string, j: number) => (
                    <span key={j} className="px-2 py-0.5 bg-surface-800/50 rounded text-[10px] text-surface-400">{t}</span>
                  ))}
                </div>
              )}
              {item.description && (
                <p className="text-[10px] text-surface-400 mt-1">{item.description}</p>
              )}
            </div>
          ))}
          {syllabus.length === 0 && (
            <p className="text-surface-500 text-xs py-4 text-center">\u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a</p>
          )}
        </div>
      )}
    </div>
  );
}
