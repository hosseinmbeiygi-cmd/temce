"use client";

import Link from "next/link";
import { usePersona } from "@/lib/persona-context";

/**
 * Persona strip on the dashboard: names the active view and offers its
 * default shortcuts. Content adapts to the preference; no data is hidden.
 */
export default function PersonaBar() {
  const { definition } = usePersona();

  return (
    <section
      aria-label="نمای کاربری"
      className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-primary-500/15 px-2 py-0.5 text-[11px] font-bold text-primary-400">
              {definition.label}
            </span>
            <span className="text-[10px] uppercase tracking-wide text-ink-3" dir="ltr">
              {definition.englishName}
            </span>
          </div>
          <p className="mt-1 text-[12px] text-ink-2">{definition.description}</p>
          <p className="mt-1 text-[10.5px] text-ink-3">{definition.riskNote}</p>
        </div>

        <nav aria-label="دسترسی سریع نمای کاربری" className="flex flex-wrap items-center gap-1.5">
          {definition.quickLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              title={link.desc}
              className="rounded-lg border border-line bg-soft/60 px-2.5 py-1.5 text-[11px] font-medium text-ink-2 transition-colors hover:border-primary-500/40 hover:text-ink"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </section>
  );
}
