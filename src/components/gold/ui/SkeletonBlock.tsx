"use client";

import { cn } from "@/lib/cn";

interface SkeletonBlockProps {
  visible?: boolean;
  className?: string;
  width?: string | number;
  height?: string | number;
}

export function SkeletonBlock({ visible = true, className, width, height }: SkeletonBlockProps) {
  if (!visible) return null;

  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-zinc-700/40",
        className
      )}
      style={{
        width: width,
        height: height,
      }}
    />
  );
}
