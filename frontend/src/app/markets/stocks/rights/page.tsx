import PagePlaceholder from "@/components/PagePlaceholder";
import { FileSignature } from "lucide-react";

export default function RightsPage() {
  return (
    <PagePlaceholder
      title="حق تقدم"
      description="پیگیری نمادهای حق تقدم سهام"
      icon={<FileSignature className="size-10 text-ink-3" />}
    />
  );
}
