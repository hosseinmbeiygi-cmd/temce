import PagePlaceholder from "@/components/PagePlaceholder";
import { CircleDollarSign } from "lucide-react";

export default function FxPage() {
  return (
    <PagePlaceholder
      title="نرخ ارز"
      description="نرخ لحظه‌ای دلار، یورو، درهم و سایر ارزها"
      icon={<CircleDollarSign className="size-10 text-ink-3" />}
    />
  );
}
