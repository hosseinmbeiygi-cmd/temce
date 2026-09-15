"use client";

import AppLayout from "@/components/layout/AppLayout";
import { Construction } from "lucide-react";

interface Props {
  title: string;
  description?: string;
  icon?: React.ReactNode;
}

export default function PagePlaceholder({ title, description, icon }: Props) {
  return (
    <AppLayout>
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-4 text-center">
        <div className="grid size-20 place-items-center rounded-2xl bg-soft">
          {icon ?? <Construction className="size-10 text-ink-3" />}
        </div>
        <h1 className="text-xl font-bold">{title}</h1>
        {description && (
          <p className="max-w-md text-sm text-ink-3">{description}</p>
        )}
        <span className="mt-2 rounded-full border border-line bg-card px-4 py-1.5 text-xs font-medium text-ink-2">
          به‌زودی
        </span>
      </div>
    </AppLayout>
  );
}
