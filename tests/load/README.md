# Load Testing with Locust

اجرای load test روی GoldDesk endpoints.

## نصب
```bash
pip install locust
```

## اجرا (Web UI)
```bash
locust -f tests/load/locustfile.py --host http://localhost:8000
# باز کردن http://localhost:8089
```

## اجرا (CLI — headless)
```bash
locust -f tests/load/locustfile.py --host http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 5m --headless
```

## اجرا با نتایج CSV
```bash
locust -f tests/load/locustfile.py --host http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 10m --headless \
  --csv=results --html=report.html
```

## سناریوها
- **Polling snapshot**: هر ۳۰ ثانیه (رایج‌ترین)
- **Hot path**: هر ۱۰ ثانیه
- **DCA calculation**: در لحظه تصمیم
- **Chat**: هر چند دقیقه
- **Portfolio**: هر ۱-۵ دقیقه

## SLO Targets
- `/snapshot`: p95 < 500ms
- `/hot`: p95 < 100ms
- `/score`: p95 < 200ms
- `/dca/plan`: p95 < 100ms
- `/chat`: p95 < 2000ms (LLM)
- Error rate < 1%
