import PagePlaceholder from "@/components/PagePlaceholder";
import { PauseCircle } from "lucide-react";

export default function SuspendedPage() {
  return (
    <PagePlaceholder
      title="نمادهای متوقف"
      description="پیگیری نمادهای متوقف از معاملات"
      icon={<PauseCircle className="size-10 text-ink-3" />}
    />
  );
}
