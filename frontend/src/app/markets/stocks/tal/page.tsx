import PagePlaceholder from "@/components/PagePlaceholder";
import { Layers } from "lucide-react";

export default function TalPage() {
  return (
    <PagePlaceholder
      title="تال"
      description="پیگیری نمادهای تال بازار سرمایه"
      icon={<Layers className="size-10 text-ink-3" />}
    />
  );
}
