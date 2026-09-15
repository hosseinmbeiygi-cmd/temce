"use client";

import { SkeletonBlock } from "@/components/dashboard/primitives";

export default function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      {/* News strip */}
      <div className="flex gap-3">
        {[1, 2, 3].map((i) => (
          <SkeletonBlock key={i} className="h-20 flex-1" />
        ))}
      </div>

      {/* Quote row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <SkeletonBlock key={i} className="h-32" />
        ))}
      </div>

      {/* Indices row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <SkeletonBlock key={i} className="h-28" />
        ))}
      </div>

      {/* Charts + side */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SkeletonBlock className="h-72 lg:col-span-2" />
        <SkeletonBlock className="h-72" />
      </div>

      {/* Bottom blocks */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <SkeletonBlock className="h-56" />
        <SkeletonBlock className="h-56" />
        <SkeletonBlock className="h-56" />
      </div>
    </div>
  );
}
