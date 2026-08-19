"use client";

import type { ReactNode } from "react";
import DashboardShell from "./DashboardShell";
import FloatingAssistant from "@/components/FloatingAssistant";

interface AppLayoutProps {
  children: ReactNode;
  title?: ReactNode;
  subtitle?: string;
  header?: ReactNode;
}

/**
 * Shared premium shell for all non-dashboard pages — composes the dashboard
 * environment (fixed navy TopNavbar, sticky TickerBar, navy/white semantic
 * tokens, geometric field, floating smart-screener pill) and adds the page
 * title/subtitle/header block plus the floating assistant.
 */
export default function AppLayout({ children, title, subtitle, header }: AppLayoutProps) {
  return (
    <>
      <DashboardShell>
        {header}
        {(title || subtitle) && (
          <div className="mb-5">
            {title && (
              <h1 className="text-[22px] font-black leading-tight text-ink">{title}</h1>
            )}
            {subtitle && <p className="mt-1 text-[12px] text-ink-3">{subtitle}</p>}
          </div>
        )}
        {children}
      </DashboardShell>
      <FloatingAssistant />
    </>
  );
}
