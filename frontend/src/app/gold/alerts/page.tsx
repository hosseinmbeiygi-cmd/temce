"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getAlertRules, getAlertEvents, seedDefaultRules, deleteAlertRule, updateAlertRule } from "@/lib/goldApi";
import { AlertRuleForm } from "@/components/gold/AlertRuleForm";
import { AlertEventList } from "@/components/gold/AlertEventList";

export default function GoldAlertsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"rules" | "events">("rules");

  const { data: rules } = useQuery({
    queryKey: ["gold", "alerts", "rules"],
    queryFn: getAlertRules,
    refetchInterval: 30_000,
  });

  const { data: events } = useQuery({
    queryKey: ["gold", "alerts", "events"],
    queryFn: () => getAlertEvents(7),
    refetchInterval: 30_000,
  });

  const onSeed = async () => {
    await seedDefaultRules();
    qc.invalidateQueries({ queryKey: ["gold", "alerts", "rules"] });
  };

  const onDelete = async (id: number) => {
    if (!confirm("حذف شود؟")) return;
    await deleteAlertRule(id);
    qc.invalidateQueries({ queryKey: ["gold", "alerts", "rules"] });
  };

  const onToggle = async (id: number, enabled: boolean) => {
    await updateAlertRule(id, { enabled });
    qc.invalidateQueries({ queryKey: ["gold", "alerts", "rules"] });
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex gap-2 border-b border-zinc-800">
        <button
          onClick={() => setTab("rules")}
          className={`px-4 py-2 text-sm border-b-2 ${
            tab === "rules" ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-400"
          }`}
        >
          قوانین ({rules?.length ?? 0})
        </button>
        <button
          onClick={() => setTab("events")}
          className={`px-4 py-2 text-sm border-b-2 ${
            tab === "events" ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-400"
          }`}
        >
          رویدادها ({events?.length ?? 0})
        </button>
      </div>

      {tab === "rules" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <AlertRuleForm onCreated={() => qc.invalidateQueries({ queryKey: ["gold", "alerts", "rules"] })} />
          <div className="lg:col-span-2 space-y-2">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-sm font-semibold text-zinc-300">قوانین موجود</h3>
              <button onClick={onSeed} className="text-xs text-amber-400 hover:text-amber-300">
                درج قوانین پیش‌فرض
              </button>
            </div>
            {(rules ?? []).map((r) => (
              <div key={r.id} className="p-3 rounded border border-zinc-700 bg-zinc-900 flex justify-between">
                <div className="flex-1">
                  <div className="text-sm text-zinc-100 font-semibold">{r.name}</div>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    {r.rule_type} {r.symbol ? `(${r.symbol})` : ""} • threshold: {r.threshold}
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-1">
                    cooldown: {r.cooldown_minutes}min • {r.channel} •{" "}
                    {r.last_fired_at ? `آخرین: ${new Date(r.last_fired_at).toLocaleString("fa-IR")}` : "ارسال نشده"}
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <button
                    onClick={() => onToggle(r.id, !r.enabled)}
                    className={`text-xs px-2 py-1 rounded ${
                      r.enabled ? "bg-emerald-700 text-emerald-100" : "bg-zinc-700 text-zinc-300"
                    }`}
                  >
                    {r.enabled ? "فعال" : "غیرفعال"}
                  </button>
                  <button onClick={() => onDelete(r.id)} className="text-xs text-rose-400 hover:text-rose-300">
                    حذف
                  </button>
                </div>
              </div>
            ))}
            {rules?.length === 0 && (
              <div className="text-zinc-500 text-sm">قانونی نیست — اولین قانون را بسازید یا پیش‌فرض‌ها را درج کنید.</div>
            )}
          </div>
        </div>
      )}

      {tab === "events" && (
        <AlertEventList
          events={events ?? []}
          onAck={() => qc.invalidateQueries({ queryKey: ["gold", "alerts", "events"] })}
        />
      )}
    </div>
  );
}
