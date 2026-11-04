// متن ثابت Phase 0 — معنا ثابت است و بازنویسی آن فقط با تأیید حقوقی مجاز است.
// «ابزار تحلیلی» عمداً حفظ شده تا با قرارداد UI قبلی (GoldNoData.test) هم‌خوان بماند.
export const GOLD_DISCLAIMER_TEXT =
  "این میز فقط ابزار تحلیلی، تصمیم‌یاری و آموزش است. سفارش اجرا نمی‌کند، دارایی نگهداری نمی‌کند، و توصیه قطعی خرید/فروش نیست. مسئولیت تصمیم با کاربر است.";

interface GoldDisclaimerProps {
  variant?: "inline" | "banner";
  className?: string;
}

export function GoldDisclaimer({ variant = "inline", className = "" }: GoldDisclaimerProps) {
  if (variant === "banner") {
    return (
      <p
        role="note"
        aria-label="سلب مسئولیت"
        className={`rounded-lg border border-zinc-700/50 bg-zinc-900/50 px-3 py-1.5 text-[10px] leading-5 text-zinc-400 ${className}`}
      >
        <span className="font-semibold text-zinc-300">سلب مسئولیت: </span>
        {GOLD_DISCLAIMER_TEXT}
      </p>
    );
  }

  return (
    <p role="note" aria-label="سلب مسئولیت" className={`text-[10px] leading-5 text-zinc-500 ${className}`}>
      {GOLD_DISCLAIMER_TEXT}
    </p>
  );
}
