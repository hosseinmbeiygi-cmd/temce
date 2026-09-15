import PagePlaceholder from "@/components/PagePlaceholder";
import { LayoutGrid } from "lucide-react";

export default function WidgetsPage() {
  return (
    <PagePlaceholder
      title="ویجت‌ها"
      description="مدیریت ویجت‌های قابل نصب"
      icon={<LayoutGrid className="size-10 text-ink-3" />}
    />
  );
}
