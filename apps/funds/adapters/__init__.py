"""Adapter Pattern برای منابع داده صندوق‌یار.

هر Adapter باید:
1. از CircuitBreaker و retry استفاده کند
2. خروجی استاندارد (SourceData) برگرداند
3. خطاها را به AdapterError تبدیل کند
4. stale بودن داده را با last_successful_fetch گزارش کند
"""
