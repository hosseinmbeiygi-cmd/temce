import PagePlaceholder from "@/components/PagePlaceholder";
import { ShoppingBag } from "lucide-react";

export default function SalesPage() {
  return (
    <PagePlaceholder
      title="فروش"
      description="پیگیری فروش‌های بازار سرمایه"
      icon={<ShoppingBag className="size-10 text-ink-3" />}
    />
  );
}
