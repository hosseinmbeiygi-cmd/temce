import PagePlaceholder from "@/components/PagePlaceholder";
import { Puzzle } from "lucide-react";

export default function PluginsPage() {
  return (
    <PagePlaceholder
      title="افزونه‌ها"
      description="مدیریت افزونه‌های سامانه"
      icon={<Puzzle className="size-10 text-ink-3" />}
    />
  );
}
