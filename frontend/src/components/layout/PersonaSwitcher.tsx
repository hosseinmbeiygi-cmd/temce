"use client";

import { PERSONAS, PERSONA_IDS, isPersonaId } from "@/lib/personas";
import { usePersona } from "@/lib/persona-context";
import { cn } from "@/lib/cn";

/**
 * Compact persona selector. The choice is a UI preference (default view,
 * density, shortcuts), never an authorization decision.
 */
export default function PersonaSwitcher({ className }: { className?: string }) {
  const { persona, definition, setPersona } = usePersona();

  return (
    <label
      className={cn(
        "hidden h-9 cursor-pointer items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-2.5 text-brand-100 transition-colors hover:bg-white/10 sm:flex",
        className,
      )}
      title={definition.description}
    >
      <span className="text-[10px] font-medium text-brand-300">نما:</span>
      <select
        aria-label="پروفایل کاربری"
        value={persona}
        onChange={(event) => {
          const next = event.target.value;
          if (isPersonaId(next)) setPersona(next);
        }}
        className="cursor-pointer bg-transparent text-xs font-bold text-brand-100 outline-none"
      >
        {PERSONA_IDS.map((id) => (
          <option key={id} value={id} className="bg-brand-950 text-white">
            {PERSONAS[id].label}
          </option>
        ))}
      </select>
    </label>
  );
}
