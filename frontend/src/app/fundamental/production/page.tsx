import PagePlaceholder from "@/components/PagePlaceholder";
import { Factory } from "lucide-react";

export default function ProductionPage() {
  return (
    <PagePlaceholder
      title="تولید و فروش"
      description="گزارش‌های تولید و فروش ماهانه شرکت‌ها"
      icon={<Factory className="size-10 text-ink-3" />}
    />
  );
}
