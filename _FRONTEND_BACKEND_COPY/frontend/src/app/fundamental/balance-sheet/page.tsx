import PagePlaceholder from "@/components/PagePlaceholder";
import { Scale } from "lucide-react";

export default function BalanceSheetPage() {
  return (
    <PagePlaceholder
      title="ترازنامه"
      description="تحلیل ترازنامه شرکت‌های بورسی"
      icon={<Scale className="size-10 text-ink-3" />}
    />
  );
}
