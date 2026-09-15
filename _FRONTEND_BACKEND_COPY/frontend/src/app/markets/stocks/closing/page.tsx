import PagePlaceholder from "@/components/PagePlaceholder";
import { Timer } from "lucide-react";

export default function ClosingPage() {
  return (
    <PagePlaceholder
      title="معاملات پایانی"
      description="پیگیری معاملات پایانی بازار"
      icon={<Timer className="size-10 text-ink-3" />}
    />
  );
}
