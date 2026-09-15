import { redirect } from "next/navigation";

// صفحهٔ چنددارایی به «بازار طلا» منتقل شد؛ مسیر قدیمی ریدایرکت می‌شود.
export default function MultiAssetRedirect() {
  redirect("/markets/gold");
}
