import PagePlaceholder from "@/components/PagePlaceholder";
import { BadgeDollarSign } from "lucide-react";

export default function DpsPage() {
  return (
    <PagePlaceholder
      title="DPS"
      description="سود نقدی هر سهم شرکت‌های بورسی"
      icon={<BadgeDollarSign className="size-10 text-ink-3" />}
    />
  );
}
