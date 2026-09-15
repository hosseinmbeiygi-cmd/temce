"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/lib/api";
import { toast } from "sonner";

// ── Types ───────────────────────────────────────────────────────────

const DECISION_TYPES = ["BUY", "WATCHLIST", "HOLD", "REDUCE", "REJECT", "NEUTRAL"] as const;

const DECISION_COLORS: Record<string, string> = {
  BUY: "#10b981",
  WATCHLIST: "#06b6d4",
  HOLD: "#f59e0b",
  REDUCE: "#f97316",
  REJECT: "#ef4444",
  NEUTRAL: "#6366f1",
};

interface DecisionFormData {
  symbol: string;
  run_id: string;
  decision: string;
  final_score: number;
  confidence: number;
  score_fundamental?: number;
  score_valuation?: number;
  score_technical?: number;
  score_liquidity?: number;
  score_orderflow?: number;
  score_micro?: number;
  score_macro?: number;
  score_event?: number;
  base_score?: number;
  penalty?: number;
  details?: string;
}

const EMPTY_FORM: DecisionFormData = {
  symbol: "",
  run_id: "",
  decision: "BUY",
  final_score: 50,
  confidence: 0.5,
};

// ── Component ───────────────────────────────────────────────────────

export default function DecisionSubmitter({ onSuccess }: { onSuccess?: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DecisionFormData>({ ...EMPTY_FORM });
  const [showAdvanced, setShowAdvanced] = useState(false);
  // SSR-safe placeholder: `Date.now()` differs between the server render and
  // the client's first render, so initializing state from it here would make
  // the placeholder attribute mismatch → hydration error → tree regenerated.
  // Start with the deterministic prefix and append the timestamp after mount.
  const [runIdPlaceholder, setRunIdPlaceholder] = useState("manual-");
  // eslint-disable-next-line react-hooks/set-state-in-effect -- hydration: add timestamp after mount
  useEffect(() => {
    setRunIdPlaceholder(`manual-${Date.now()}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const mutation = useMutation({
    mutationFn: async (data: DecisionFormData) => {
      const body: Record<string, unknown> = {
        symbol: data.symbol.trim(),
        run_id: data.run_id.trim() || runIdPlaceholder,
        decision: data.decision,
        final_score: data.final_score,
        confidence: data.confidence,
      };

      // Optional fields
      if (data.score_fundamental !== undefined) body.score_fundamental = data.score_fundamental;
      if (data.score_valuation !== undefined) body.score_valuation = data.score_valuation;
      if (data.score_technical !== undefined) body.score_technical = data.score_technical;
      if (data.score_liquidity !== undefined) body.score_liquidity = data.score_liquidity;
      if (data.score_orderflow !== undefined) body.score_orderflow = data.score_orderflow;
      if (data.score_micro !== undefined) body.score_micro = data.score_micro;
      if (data.score_macro !== undefined) body.score_macro = data.score_macro;
      if (data.score_event !== undefined) body.score_event = data.score_event;
      if (data.base_score !== undefined) body.base_score = data.base_score;
      if (data.penalty !== undefined) body.penalty = data.penalty;

      // Parse details JSON if provided
      if (data.details?.trim()) {
        try {
          body.details = JSON.parse(data.details);
        } catch {
          body.details = { reasons: [data.details] };
        }
      }

      return apiPost("/decision-engine/decisions", body);
    },
    onSuccess: () => {
      toast.success(`تصمیم ${form.decision} برای ${form.symbol} با موفقیت ذخیره شد`);
      setForm({ ...EMPTY_FORM, run_id: runIdPlaceholder });
      queryClient.invalidateQueries({ queryKey: ["dss-decisions"] });
      onSuccess?.();
    },
    onError: (err: Error) => {
      toast.error(`خطا در ذخیره تصمیم: ${err.message}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.symbol.trim()) {
      toast.error("لطفاً نماد را وارد کنید");
      return;
    }
    mutation.mutate(form);
  };

  const updateField = (field: keyof DecisionFormData, value: string | number | undefined) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="glass-card p-4">
      <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
        <span className="material-icons text-sm">add_circle</span>
        ثبت تصمیم دستی
      </h2>

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Row 1: Symbol + Decision + Score */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
          <div>
            <label className="text-[9px] font-medium text-surface-500 mb-1 block">نماد</label>
            <input
              type="text"
              value={form.symbol}
              onChange={(e) => updateField("symbol", e.target.value)}
              placeholder="مثال: فولاد"
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 placeholder-surface-500 outline-none focus:border-primary-500 transition-colors"
              dir="ltr"
            />
          </div>
          <div>
            <label className="text-[9px] font-medium text-surface-500 mb-1 block">تصمیم</label>
            <select
              value={form.decision}
              onChange={(e) => updateField("decision", e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 outline-none focus:border-primary-500 transition-colors"
              style={{ borderColor: DECISION_COLORS[form.decision] + "40" }}
            >
              {DECISION_TYPES.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[9px] font-medium text-surface-500 mb-1 block">امتیاز نهایی</label>
            <input
              type="number"
              value={form.final_score}
              onChange={(e) => updateField("final_score", parseFloat(e.target.value) || 0)}
              min={0}
              max={100}
              step={0.5}
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 outline-none focus:border-primary-500 transition-colors"
            />
          </div>
          <div>
            <label className="text-[9px] font-medium text-surface-500 mb-1 block">اطمینان (۰-۱)</label>
            <input
              type="number"
              value={form.confidence}
              onChange={(e) => updateField("confidence", parseFloat(e.target.value) || 0)}
              min={0}
              max={1}
              step={0.05}
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 outline-none focus:border-primary-500 transition-colors"
            />
          </div>
        </div>

        {/* Run ID (auto-generated if empty) */}
        <div>
          <label className="text-[9px] font-medium text-surface-500 mb-1 block">
            شناسه اجرا (خالی = خودکار)
          </label>
          <input
            type="text"
            value={form.run_id}
            onChange={(e) => updateField("run_id", e.target.value)}
            placeholder={runIdPlaceholder}
            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-xs text-surface-100 placeholder-surface-500 outline-none focus:border-primary-500 transition-colors"
            dir="ltr"
          />
        </div>

        {/* Advanced toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-[10px] text-surface-500 hover:text-surface-300 transition-colors"
        >
          <span className="material-icons text-xs">{showAdvanced ? "expand_less" : "expand_more"}</span>
          {showAdvanced ? "پنهان کردن امتیازات پیشرفته" : "نمایش امتیازات پیشرفته"}
        </button>

        {/* Advanced scores */}
        {showAdvanced && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 rounded-xl bg-surface-800/30 border border-surface-700/30">
            {[
              { field: "score_fundamental" as const, label: "بنیادی (S_F)" },
              { field: "score_valuation" as const, label: "ارزش‌گذاری (S_V)" },
              { field: "score_technical" as const, label: "تکنیکال (S_T)" },
              { field: "score_liquidity" as const, label: "نقدشوندگی (S_L)" },
              { field: "score_orderflow" as const, label: "جریان پول (S_O)" },
              { field: "score_micro" as const, label: "میکرو (S_M)" },
              { field: "score_macro" as const, label: "کلان (S_K)" },
              { field: "score_event" as const, label: "رویدادی (S_E)" },
            ].map((s) => (
              <div key={s.field}>
                <label className="text-[8px] font-medium text-surface-500 mb-0.5 block">{s.label}</label>
                <input
                  type="number"
                  value={form[s.field] ?? ""}
                  onChange={(e) => updateField(s.field, e.target.value ? parseFloat(e.target.value) : undefined)}
                  min={0}
                  max={100}
                  step={1}
                  className="w-full bg-surface-800/50 border border-surface-700/30 rounded-lg px-2 py-1.5 text-[10px] text-surface-100 outline-none focus:border-primary-500 transition-colors"
                />
              </div>
            ))}
            <div>
              <label className="text-[8px] font-medium text-surface-500 mb-0.5 block">BaseScore</label>
              <input
                type="number"
                value={form.base_score ?? ""}
                onChange={(e) => updateField("base_score", e.target.value ? parseFloat(e.target.value) : undefined)}
                min={0} max={100} step={1}
                className="w-full bg-surface-800/50 border border-surface-700/30 rounded-lg px-2 py-1.5 text-[10px] text-surface-100 outline-none focus:border-primary-500 transition-colors"
              />
            </div>
            <div>
              <label className="text-[8px] font-medium text-surface-500 mb-0.5 block">Penalty</label>
              <input
                type="number"
                value={form.penalty ?? ""}
                onChange={(e) => updateField("penalty", e.target.value ? parseFloat(e.target.value) : undefined)}
                min={0} max={0.35} step={0.01}
                className="w-full bg-surface-800/50 border border-surface-700/30 rounded-lg px-2 py-1.5 text-[10px] text-surface-100 outline-none focus:border-primary-500 transition-colors"
              />
            </div>
            <div className="col-span-2 sm:col-span-4">
              <label className="text-[8px] font-medium text-surface-500 mb-0.5 block">
                جزئیات (JSON یا متن)
              </label>
              <textarea
                value={form.details ?? ""}
                onChange={(e) => updateField("details", e.target.value)}
                rows={2}
                placeholder='{"reasons": ["نقدشوندگی بالا"], "reason_codes": ["LIQ-01"]}'
                className="w-full bg-surface-800/50 border border-surface-700/30 rounded-lg px-2 py-1.5 text-[10px] text-surface-100 placeholder-surface-500 outline-none focus:border-primary-500 transition-colors font-mono"
              />
            </div>
          </div>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={mutation.isPending || !form.symbol.trim()}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-white transition-all disabled:opacity-40"
          style={{ backgroundColor: DECISION_COLORS[form.decision] }}
        >
          {mutation.isPending ? (
            <>
              <span className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              در حال ذخیره...
            </>
          ) : (
            <>
              <span className="material-icons text-sm">save</span>
              ثبت تصمیم {form.decision} برای {form.symbol || "..."}
            </>
          )}
        </button>
      </form>
    </div>
  );
}
