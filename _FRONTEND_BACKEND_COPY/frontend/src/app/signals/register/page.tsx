import PagePlaceholder from "@/components/PagePlaceholder";
import { PenLine } from "lucide-react";

export default function RegisterSignalPage() {
  return (
    <PagePlaceholder
      title="ثبت سیگنال"
      description="ثبت سیگنال دستی برای نمادها"
      icon={<PenLine className="size-10 text-ink-3" />}
    />
  );
}
