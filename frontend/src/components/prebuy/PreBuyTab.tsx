"use client";

/**
 * The «برگهٔ خرید» tab on a symbol page, and the auth boundary around it.
 *
 * Without this wrapper the tab would fire user-scoped queries at `/pre-buy/sheets` for
 * an anonymous visitor, and the API client answers a 401 by redirecting to the login
 * page — from a chart the user was just reading. So the gate is checked here, before
 * any sheet query is enabled.
 */

import Link from "next/link";
import { Loader2, LogIn } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Panel } from "./ui";
import { DecisionSheet } from "./DecisionSheet";

export function PreBuyTab({ symbol }: { symbol: string }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-6 text-[12px] text-surface-400">
        <Loader2 className="w-4 h-4 animate-spin" /> بررسی نشست…
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Panel
        title="برگهٔ تصمیم در حساب شما نگه داشته می‌شود"
        desc="پاسخ‌ها، شواهد زنده و قضاوت هر برگه به حساب شما ثبت می‌شود تا بعداً قابل بازبینی بماند."
      >
        <Link
          href={`/auth/login?redirect=${encodeURIComponent(`/symbol/${symbol}`)}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3.5 py-2 text-[12px] font-bold text-white hover:bg-primary-500"
        >
          <LogIn className="w-4 h-4" /> ورود و باز کردن برگهٔ {symbol}
        </Link>
      </Panel>
    );
  }

  return <DecisionSheet symbol={symbol} />;
}
