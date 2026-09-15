import PagePlaceholder from "@/components/PagePlaceholder";
import { Percent } from "lucide-react";

export default function RatiosPage() {
  return (
    <PagePlaceholder
      title="نسبت‌های مالی"
      description="نسبت‌های مالی کلیدی شرکت‌های بورسی"
      icon={<Percent className="size-10 text-ink-3" />}
    />
  );
}
