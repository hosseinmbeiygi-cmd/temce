"use client";

import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import type { Snapshot } from "@/types/gold";

export default function GoldPhase2UI({ snapshot, isLoading }: { snapshot?: Snapshot; isLoading?: boolean }) {
  if (isLoading && !snapshot) {
    return <SkeletonBlock visible className="h-64 w-full" />;
  }

  if (!snapshot) {
    return (
      <div className="rounded-lg border border-zinc-700/50 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
        اسنپ‌شات بازار در دسترس نیست.
      </div>
    );
  }

  return null;
}