import PagePlaceholder from "@/components/PagePlaceholder";
import { Landmark } from "lucide-react";

export default function StocksBondsPage() {
  return (
    <PagePlaceholder
      title="اوراق"
      description="پیگیری اوراق بدهی و خزانه"
      icon={<Landmark className="size-10 text-ink-3" />}
    />
  );
}
