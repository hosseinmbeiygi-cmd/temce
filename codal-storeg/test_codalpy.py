from codalpy import Codal

# ایجاد وهله با پارامترهای اجباری
codal = Codal(query="", category="")

print("📋 لیست متدهای موجود در Codal:")
methods = [m for m in dir(codal) if callable(getattr(codal, m)) and not m.startswith('_')]
for m in methods:
    print(f"  - {m}")