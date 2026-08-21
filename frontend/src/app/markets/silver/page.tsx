import PagePlaceholder from "@/components/PagePlaceholder";
import { Coins } from "lucide-react";

export default function SilverPage() {
  return (
    <PagePlaceholder
      title="بازار نقره"
      description="انس نقره و صندوق‌های مرتبط"
      icon={<Coins className="size-10 text-ink-3" />}
    />
  );
}
