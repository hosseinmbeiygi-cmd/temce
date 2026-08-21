import PagePlaceholder from "@/components/PagePlaceholder";
import { ArrowUpCircle } from "lucide-react";

export default function CapitalIncreasePage() {
  return (
    <PagePlaceholder
      title="افزایش سرمایه"
      description="پیگیری افزایش سرمایه شرکت‌های بورسی"
      icon={<ArrowUpCircle className="size-10 text-ink-3" />}
    />
  );
}
