# Concurrency & Alert Static Audit

- POST/creation endpoints: 5
- idempotency-key hits: 7
- unique constraints: 21
- lock/transaction hits: 109

Verdict: partial — P0: add Idempotency-Key header + DB unique constraint on (client_key) for orders/alerts/backtest jobs.
