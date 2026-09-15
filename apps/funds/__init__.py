"""سامانه صندوق‌یار — پایش هوشمند صندوق‌های سرمایه‌گذاری ایران.

این پکیج شامل لایه‌های زیر است:
- adapters: اتصال به فیپیران، TSETMC، کدال (Adapter Pattern + Circuit Breaker)
- metrics: موتور محاسبه ۵۶ شاخص در ۵ لایه
- scoring: موتور امتیازدهی وزن‌دار با Config Versioning
- services: orchestration سطح بالا
- api: endpointهای FastAPI

قانون حاکم: شفافیت کامل. هیچ شاخصی مخفی نیست. فرمول و وزن هر سنجه علنی است.
"""

__version__ = "0.1.0"
