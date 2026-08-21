import PagePlaceholder from "@/components/PagePlaceholder";
import { Gem } from "lucide-react";

export default function GoldPage() {
  return (
    <PagePlaceholder
      title="بازار طلا"
      description="انس، سکه و طلای ۱۸ عیار"
      icon={<Gem className="size-10 text-ink-3" />}
    />
  );
}
