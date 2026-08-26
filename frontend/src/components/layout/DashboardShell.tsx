"use client";

import type { ReactNode } from "react";
import TopNavbar from "./TopNavbar";
import TickerBar from "./TickerBar";
import SmartScreenerFab from "./SmartScreenerFab";

export default function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="dash-field min-h-screen bg-canvas text-ink transition-colors duration-300">
      <TopNavbar />
      {/* TopNavbar is fixed and therefore removed from normal flow. Reserve
          its 56px height so the live ticker and page content cannot slide
          underneath it on the initial render. */}
      <div className="h-14 shrink-0" aria-hidden="true" />
      <TickerBar />
      <main className="relative z-10 mx-auto max-w-[1600px] px-3 pb-20 pt-8 lg:px-5">
        {children}
      </main>
      <SmartScreenerFab />
    </div>
  );
}
