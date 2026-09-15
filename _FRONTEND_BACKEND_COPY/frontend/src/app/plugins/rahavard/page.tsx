import PagePlaceholder from "@/components/PagePlaceholder";
import { Plug } from "lucide-react";

export default function RahavardPage() {
  return (
    <PagePlaceholder
      title="افزودن رهاورد"
      description="اتصال به نرم‌افزار رهاورد ۳۶۵"
      icon={<Plug className="size-10 text-ink-3" />}
    />
  );
}
