import PagePlaceholder from "@/components/PagePlaceholder";
import { Home } from "lucide-react";

export default function MaskanPage() {
  return (
    <PagePlaceholder
      title="امتیاز تسهیلات مسکن"
      description="پیگیری امتیاز تسهیلات مسکن"
      icon={<Home className="size-10 text-ink-3" />}
    />
  );
}
