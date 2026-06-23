"use client";

interface SkeletonProps {
  className?: string;
}

export default function Skeleton({ className }: SkeletonProps) {
  return <div className={`bg-surface-800 animate-pulse rounded ${className}`} />;
}
