import PagePlaceholder from "@/components/PagePlaceholder";
import { TrendingUp } from "lucide-react";

export default function FuturesPage() {
  return (
    <PagePlaceholder
      title="قراردادهای آتی"
      description="پیگیری قراردادهای آتی سکه طلا و سایر کالاها"
      icon={<TrendingUp className="size-10 text-ink-3" />}
    />
  );
}
