"use client";

import type { AssetBlock } from "@/types/gold";
import CanonicalCoinBubbleTable from "@/app/gold/components/CoinBubbleTable";

interface Props {
  coins: Record<string, AssetBlock>;
  className?: string;
}

/**
 * F8 — نسخهٔ تکراری حذف شد، منبع حقیقت یکی است.
 *
 * دو پیاده‌سازی مستقلِ «جدول حباب سکه» در repo وجود داشت:
 *   `app/gold/components/CoinBubbleTable.tsx` (که صفحهٔ فرماندهی استفاده می‌کرد)
 *   و همین فایل، که هیچ‌جا import نمی‌شد. نسخهٔ مرتفع‌شده باگ واقعی داشت:
 *   `c.market_price.toLocaleString()` روی null می‌شکست و
 *   `c.implied_usd ? … : "—"` مقدار صفرِ واقعی را «گم‌شده» می‌شمرد.
 *
 * این فایل فقط یک adapter نازک است: prop shape قدیمی را نگه می‌دارد و رندر را
 * به منبع حقیقت می‌سپارد، پس دو نسخه دیگر نمی‌توانند از هم واگرا شوند.
 * حذف فیزیکی فایل (به‌جای تبدیل به adapter) عمداً به صاحب repo واگذار شده است.
 */
export function CoinBubbleTable({ coins, className }: Props) {
  return (
    <div className={className}>
      <CanonicalCoinBubbleTable data={Object.values(coins ?? {})} />
    </div>
  );
}

export default CoinBubbleTable;
