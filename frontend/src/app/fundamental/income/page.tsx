import PagePlaceholder from "@/components/PagePlaceholder";
import { TrendingUp } from "lucide-react";

export default function IncomePage() {
  return (
    <PagePlaceholder
      title="سود و زیان"
      description="تحلیل صورت سود و زیان شرکت‌ها"
      icon={<TrendingUp className="size-10 text-ink-3" />}
    />
  );
}
