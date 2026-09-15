import PagePlaceholder from "@/components/PagePlaceholder";
import { Wallet } from "lucide-react";

export default function CashflowPage() {
  return (
    <PagePlaceholder
      title="گردش وجوه نقد"
      description="تحلیل صورت جریان وجوه نقد شرکت‌ها"
      icon={<Wallet className="size-10 text-ink-3" />}
    />
  );
}
