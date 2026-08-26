# 3-3 — سه محیط + CI/CD — فاز ۳

> مالک: DevOps

## محیط‌ها
| محیط | DB | BrsApi | داده |
|------|----|--------|------|
| dev | local | mock | مصنوعی |
| test | staging | BrsApi staging (یا mock) | کپی ناشناس‌شده |
| prod | prod (Timescale) | BrsApi prod | واقعی + raw_store |

- داده prod هرگز در test/dev کپی نمی‌شود (حریم خصوصی)
- Secret هر محیط جدا در Vault

## CI/CD
```
PR → ruff + pytest (41+20) + npm build → staging (auto) → prod (manual + مالک ریسک)
```
- blue-green deploy + rollback <5m
- هر deploy: `calc_version` بامپ + migration

## معیار
- تست نفوذ: دسترسی dev به prod → 403
