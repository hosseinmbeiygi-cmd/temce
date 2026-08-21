import PagePlaceholder from "@/components/PagePlaceholder";
import { BadgePercent } from "lucide-react";

export default function DividendsPage() {
  return (
    <PagePlaceholder
      title="پرداخت سود نقدی"
      description="پیگیری پرداخت سود نقدی شرکت‌ها"
      icon={<BadgePercent className="size-10 text-ink-3" />}
    />
  );
}
