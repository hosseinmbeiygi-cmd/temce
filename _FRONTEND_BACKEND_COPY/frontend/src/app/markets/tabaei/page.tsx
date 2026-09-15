import PagePlaceholder from "@/components/PagePlaceholder";
import { Layers } from "lucide-react";

export default function TabaeiPage() {
  return (
    <PagePlaceholder
      title="تبعی"
      description="پیگیری اوراق تبعی بازار سرمایه"
      icon={<Layers className="size-10 text-ink-3" />}
    />
  );
}
