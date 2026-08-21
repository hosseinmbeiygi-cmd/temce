import PagePlaceholder from "@/components/PagePlaceholder";
import { ArrowLeftRight } from "lucide-react";

export default function DataTransferPage() {
  return (
    <PagePlaceholder
      title="انتقال داده"
      description="انتقال داده بین سامانه‌های مختلف"
      icon={<ArrowLeftRight className="size-10 text-ink-3" />}
    />
  );
}
