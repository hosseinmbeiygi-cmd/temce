import PagePlaceholder from "@/components/PagePlaceholder";
import { TrendingUp } from "lucide-react";

export default function SalafPage() {
  return (
    <PagePlaceholder
      title="سلف و موازی"
      description="قراردادهای سلف و اوراق موازی بورس کالا"
      icon={<TrendingUp className="size-10 text-ink-3" />}
    />
  );
}
