"use client";

import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";

export default function HoldersPage() {
  return (
    <AppLayout>
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">سهامداران عمده</h1>
        <Card className="p-4">
          <p className="text-muted-foreground">اطلاعات سهامداران عمده نمادهای بورسی</p>
        </Card>
      </div>
    </AppLayout>
  );
}
