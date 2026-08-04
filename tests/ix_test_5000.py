# fix_test_5000.py
import os
import re


def fix_file():
    filepath = 'tests/test_5000_questions.py'

    if not os.path.exists(filepath):
        print(f"⚠️ File not found: {filepath}")
        return

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # 1. رفع خطاهای F821 - تعریف متغیرهای undefined

    # خط 201: Q(cat, f"A{i+1}: score {sname} = {score}")
    # مشکل: 'score' تعریف نشده است
    content = content.replace(
        'Q(cat, f"A{i+1}: score {sname} = {score}")',
        'Q(cat, f"A{i+1}: score {sname} = {val}")'
    )

    # خط 316: Q(cat, f"A{i+1}: confidence = {confidence}")
    # مشکل: 'confidence' تعریف نشده است
    content = content.replace(
        'Q(cat, f"A{i+1}: confidence = {confidence}")',
        'Q(cat, f"A{i+1}: confidence = {conf}")'
    )

    # خط 1215: رشته ناقص
    # Q(cat, f"A{200+i+1}: extreme OK", "PASS", f"smc = {smc}")
    content = re.sub(
        r'Q\(cat, f"A{200\+i\+1}: extreme OK", "PASS", f"smc = \(',
        r'Q(cat, f"A{200+i+1}: extreme OK", "PASS", f"smc = {smc}")',
        content
    )

    # 2. رفع خطاهای رشته‌های ناقص
    # پیدا کردن و اصلاح همه Q(... که با ( ختم می‌شوند
    content = re.sub(
        r'Q\(cat, f"A{\d+\+i\+1}: score = \(',
        r'Q(cat, f"A{num+i+1}: score = {val}")',
        content
    )

    content = re.sub(
        r'Q\(cat, f"A{\d+\+i\+1}: confidence = \(',
        r'Q(cat, f"A{num+i+1}: confidence = {conf}")',
        content
    )

    content = re.sub(
        r'Q\(cat, f"A{\d+\+i\+1}: extreme OK", "PASS", f"smc = \(',
        r'Q(cat, f"A{num+i+1}: extreme OK", "PASS", f"smc = {smc}")',
        content
    )

    content = re.sub(
        r'Q\(cat, f"A{\d+\+i\+1}: zero vol/price OK", "PASS", f"smc = \(',
        r'Q(cat, f"A{num+i+1}: zero vol/price OK", "PASS", f"smc = {smc}")',
        content
    )

    # 3. رفع خطای Q(cat, f"Q{cat}: .*? = (")
    content = re.sub(
        r'Q\(cat, f"Q{cat}: .*? = \(',
        r'Q(cat, f"Q{cat}: ... = {value}")',
        content
    )

    # 4. رفع خطاهای f-string با بک‌اسلش
    # print(f"  Ensemble: {result['test']['action']} conf = {confidence}")
    content = re.sub(
        r'print\(f"  Ensemble: \{result\[\'test\'\]\[\'action\'\]\} conf = \(',
        r'print(f"  Ensemble: {result[\'test\'][\'action\']} conf = {confidence}")',
        content
    )

    # 5. رفع خطای D700
    # Q(cat, f"... = {value}") -> Q(cat, f"... = {value}")
    content = re.sub(
        r'Q\(cat, f"\.\.\. = {value}"\)',
        r'Q(cat, f"... = {value}")',
        content
    )

    # 6. رفع خطای D700 واقعی
    content = re.sub(
        r'Q\(cat, f"D{700\+i\+1}: max drawdown", "PASS", f"mdd={mdd:\.2f}%", dur\)',
        r'Q(cat, f"D{700+i+1}: max drawdown", "PASS", f"mdd={mdd:.2f}%", dur)',
        content
    )

    # 7. رفع خطای print(f"  Screeened ...")
    content = re.sub(
        r'print\(f"  Screened \{len\(results\)\} symbols, total = \(',
        r'print(f"  Screened {len(results)} symbols, total = {total}")',
        content
    )

    # 8. رفع خطای 'total')}"
    content = content.replace(
        "'total')}\"",
        "'total')}\""
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Fixed: {filepath}")

if __name__ == "__main__":
    print("="*70)
    print("🔧 Fixing test_5000_questions.py")
    print("="*70)
    fix_file()
    print("\n✅ Done!")
    print("\n📋 Now run:")
    print("   black tests/test_5000_questions.py --line-length 120")
    print("   flake8 tests/test_5000_questions.py --select=E9,F821 --statistics")
