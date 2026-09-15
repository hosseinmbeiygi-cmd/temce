import PagePlaceholder from "@/components/PagePlaceholder";
import { Calculator } from "lucide-react";

export default function EpsPage() {
  return (
    <PagePlaceholder
      title="EPS"
      description="سود هر سهم شرکت‌های بورسی"
      icon={<Calculator className="size-10 text-ink-3" />}
    />
  );
}
