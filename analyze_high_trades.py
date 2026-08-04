import contextlib
import json
from pathlib import Path

# ========== تنظیمات ==========
DATA_DIR = "backtest_data_all"
OUTPUT_FILE = "symbols_high_liquidity.json"

# ========== معیارهای اصلی ==========
MIN_TRADES = 4000      # تعداد معاملات روزانه
MIN_VOLUME = 10_000_000   # حداقل حجم معاملات (۱۰ میلیون سهم)
MIN_VALUE = 100_000_000_000  # حداقل ارزش معاملات (۱۰۰ میلیارد تومان = ۱۰۰,۰۰۰,۰۰۰,۰۰۰)
MIN_DAYS_PERCENT = 80   # حداقل درصد روزهایی که معیارها برآورده شوند
MIN_DAYS = 90            # حداقل روزهای معاملاتی

# ========== محدود کردن تعداد ==========
TOP_N = 50  # تعداد نمادهای برتر
# ===================================

def load_history_files():
    data_dir = Path(DATA_DIR)
    if not data_dir.exists():
        print(f"❌ پوشه '{DATA_DIR}' وجود ندارد!")
        return {}

    files = list(data_dir.glob("*.json"))
    print(f"✅ {len(files)} فایل JSON در پوشه '{DATA_DIR}' یافت شد.")

    all_data = {}
    for file in files:
        symbol = file.stem
        try:
            with open(file, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0 and 'tno' in data[0]:
                all_data[symbol] = data
        except Exception as e:
            print(f"❌ خطا در خواندن {file.name}: {e}")

    print(f"📊 {len(all_data)} نماد دارای داده‌های معتبر تاریخچه.")
    return all_data

def analyze_symbol(symbol, data):
    tno_list = []
    tvol_list = []
    tval_list = []

    for day in data:
        tno = day.get('tno')
        tvol = day.get('tvol')
        tval = day.get('tval')

        if tno is not None:
            with contextlib.suppress(BaseException):
                tno_list.append(float(tno))
        if tvol is not None:
            with contextlib.suppress(BaseException):
                tvol_list.append(float(tvol))
        if tval is not None:
            with contextlib.suppress(BaseException):
                tval_list.append(float(tval))

    if len(tno_list) < MIN_DAYS:
        return None

    # محاسبه میانگین‌ها
    avg_tno = sum(tno_list) / len(tno_list)
    avg_tvol = sum(tvol_list) / len(tvol_list) if tvol_list else 0
    avg_tval = sum(tval_list) / len(tval_list) if tval_list else 0

    # تعداد روزهایی که هر معیار برآورده شده
    days_tno = sum(1 for t in tno_list if t > MIN_TRADES)
    days_tvol = sum(1 for t in tvol_list if t > MIN_VOLUME) if tvol_list else 0
    days_tval = sum(1 for t in tval_list if t > MIN_VALUE) if tval_list else 0

    # درصد برآورده شدن هر معیار
    percent_tno = (days_tno / len(tno_list)) * 100
    percent_tvol = (days_tvol / len(tno_list)) * 100 if tvol_list else 0
    percent_tval = (days_tval / len(tno_list)) * 100 if tval_list else 0

    # معیار ترکیبی: حداقل ۲ معیار از ۳ باید برآورده شوند
    criteria_met = sum([
        percent_tno >= MIN_DAYS_PERCENT,
        percent_tvol >= MIN_DAYS_PERCENT,
        percent_tval >= MIN_DAYS_PERCENT
    ])

    meets_criteria = criteria_met >= 2

    # امتیاز نقدشوندگی (برای رتبه‌بندی)
    liquidity_score = (
        (avg_tno / 1000) * 0.3 +
        (avg_tvol / 10_000_000) * 0.3 +
        (avg_tval / 1_000_000_000) * 0.4
    )

    return {
        'symbol': symbol,
        'total_days': len(tno_list),
        'avg_tno': avg_tno,
        'avg_tvol': avg_tvol,
        'avg_tval': avg_tval,
        'max_tno': max(tno_list) if tno_list else 0,
        'max_tvol': max(tvol_list) if tvol_list else 0,
        'max_tval': max(tval_list) if tval_list else 0,
        'percent_tno': percent_tno,
        'percent_tvol': percent_tvol,
        'percent_tval': percent_tval,
        'days_tno': days_tno,
        'days_tvol': days_tvol,
        'days_tval': days_tval,
        'criteria_met': criteria_met,
        'liquidity_score': liquidity_score,
        'meets_criteria': meets_criteria
    }

def main():
    print("=" * 70)
    print("🔍 تحلیل نمادهای با نقدشوندگی بالا (تعداد معاملات + حجم + ارزش)")
    print("=" * 70)
    print(f"📊 آستانه تعداد معاملات (tno): {MIN_TRADES:,}")
    print(f"📊 آستانه حجم معاملات (tvol): {MIN_VOLUME:,}")
    print(f"📊 آستانه ارزش معاملات (tval): {MIN_VALUE:,}")
    print(f"📊 حداقل درصد روزها: {MIN_DAYS_PERCENT}%")
    print(f"📊 حداقل روزهای معاملاتی: {MIN_DAYS}")
    print("📊 معیار ترکیبی: حداقل ۲ معیار از ۳ برآورده شود")
    if TOP_N:
        print(f"📊 فقط {TOP_N} نماد برتر نمایش داده می‌شوند.")
    print("=" * 70)

    all_data = load_history_files()
    if not all_data:
        print("❌ داده‌ای برای تحلیل وجود ندارد.")
        return

    results = []
    for symbol, data in all_data.items():
        analysis = analyze_symbol(symbol, data)
        if analysis:
            results.append(analysis)

    print(f"✅ {len(results)} نماد دارای حداقل {MIN_DAYS} روز معاملاتی هستند.")

    # فیلتر کردن و مرتب‌سازی بر اساس امتیاز نقدشوندگی
    qualified = [r for r in results if r['meets_criteria']]
    qualified.sort(key=lambda x: x['liquidity_score'], reverse=True)

    if TOP_N and len(qualified) > TOP_N:
        original_count = len(qualified)
        qualified = qualified[:TOP_N]
        print(f"\n⚠️ تعداد نمادها از {original_count} به {TOP_N} محدود شد.")

    print("\n" + "=" * 70)
    print(f"🏆 {len(qualified)} نماد برتر با نقدشوندگی بالا:")
    print("=" * 70)

    if qualified:
        print(f"{'#':<4} {'نماد':<10} {'میانگین tno':<12} {'میانگین tvol':<15} {'میانگین tval':<15} {'امتیاز':<10}")
        print("-" * 80)
        for i, r in enumerate(qualified, 1):
            print(f"{i:<4} {r['symbol']:<10} {r['avg_tno']:>10,.0f} {r['avg_tvol']:>13,.0f} {r['avg_tval']:>13,.0f} {r['liquidity_score']:>8.2f}")

        # نمایش نمادهایی که بالاترین امتیاز را دارند
        print("\n🔹 نمادهای با بالاترین امتیاز نقدشوندگی:")
        for r in qualified[:10]:
            print(f"   - {r['symbol']}: امتیاز {r['liquidity_score']:.2f} (tno: {r['avg_tno']:.0f}, tvol: {r['avg_tvol']:.0f}, tval: {r['avg_tval']:.0f})")

        # ذخیره در فایل
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'criteria': {
                    'min_trades': MIN_TRADES,
                    'min_volume': MIN_VOLUME,
                    'min_value': MIN_VALUE,
                    'min_days_percent': MIN_DAYS_PERCENT,
                    'min_days': MIN_DAYS,
                    'top_n': TOP_N
                },
                'total_symbols': len(results),
                'qualified_symbols': len(qualified),
                'symbols': qualified
            }, f, ensure_ascii=False, indent=2)
        print(f"\n📁 نتایج کامل در '{OUTPUT_FILE}' ذخیره شد.")
    else:
        print("❌ هیچ نمادی با معیارهای مورد نظر یافت نشد.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 متوقف شد توسط کاربر.")
