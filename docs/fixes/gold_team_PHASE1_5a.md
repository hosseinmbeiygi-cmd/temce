# GoldDesk — فاز ۱.۵a: طراحی Ownership (فقط‌خواندنی)

**تاریخ:** ۲۰۲۶-۱۱-۰۹  
**نوع:** طراحی (بدون تغییر کد/migration)  
**worktree:** `fix/gold-team`  
**مبنای کد:** commit `b63affe3`

---

## ۱. خلاصهٔ اجرایی

مدل ownership کنونی **API-layer** را درست پیاده می‌کند (تمام ۱۲+ endpoint شخصی
از `owned_scope()` استفاده می‌کنند) اما **schema-layer** آن را
تضمین نمی‌کند: ستون `user_id` در همهٔ جداول شخصی `nullable=True` است و
ردیف‌های legacy بدون user_id وجود دارند. این طراحی گام‌های Phase 1.5b را
مشخص می‌کند.

**هیچ تغییری در کد، migration یا داده تا تأیید صریح مالک اعمال نمی‌شود.**

---

## ۲. وضعیت فعلی — اجزای کلیدی

### ۲.۱ تابع `owned_scope()` و `current_user_id()`

```python
# apps/api/dependencies.py:321
def owned_scope(current_user: dict) -> str | None:
    """None = بدون فیلتر (فقط admin); str = user_id (کاربر عادی)."""
    if has_role(current_user.get("roles", []), "admin"):
        return None
    return current_user_id(current_user)
```

**تفسیر:**
- `None` → admin: **هیچ WHERE اضافه نمی‌شود** → همهٔ ردیف‌ها (شامل `user_id=NULL`)
- `str` → کاربر عادی: `WHERE user_id = '<sub>'`

### ۲.۲ جداول شخصی و وضعیت `user_id`

| جدول | ستون | nullable | index | constraint |
|------|------|---------|-------|-----------|
| `gold_holdings` | `user_id` | ✓ | idx | — |
| `gold_trades` | `user_id` | ✓ | idx | — |
| `gold_alert_rules` | `user_id` | ✓ | idx | — |
| `gold_alert_events` | `user_id` | ✓ | idx | — |
| `gold_dca_plans` | `user_id` | ✓ | idx | — |
| `gold_portfolio_history` | `user_id` | ✓ | composite unique(user_id, as_of) | — |
| `gold_snapshot_cache` | — | — | — | داده عمومی (بدون owner) ✓ |
| `gold_fund_nav` | — | — | — | داده بازار (بدون owner) ✓ |

> **یافتهٔ کلیدی:** هیچ constraint دیتابیسی وجود ندارد که از درج ردیف با `user_id=NULL`
> جلوگیری کند. API layer اکنون همیشه `user_id` را ست می‌کند (با `current_user_id()`),
> اما ردیف‌های legacy از قبل از این اعمال ممکن است `NULL` باشند.

### ۲.۳ الگوهای اعمال ownership در API

**الگوی A — لیست (صحیح):**
```python
scope = owned_scope(current_user)
stmt = select(Model).order_by(...)
if scope is not None:
    stmt = stmt.where(Model.user_id == scope)
```
استفاده در: `/alerts/rules`, `/alerts/events`, `/portfolio/holdings`,
`/portfolio/trades`, `/portfolio/dca`

**الگوی B — single-item (صحیح):**
```python
scope = owned_scope(current_user)
item = await session.get(Model, item_id)
if scope is not None and getattr(item, "user_id", None) != scope:
    raise HTTPException(404, "not found")
```
استفاده در: `/portfolio/holdings/{id}` (delete, update), `/portfolio/dca/{id}`

**الگوی C — service layer با `allow_any_owner` (صحیح اما نیاز به مستندسازی):**
```python
# api.py:1446
allow_any_owner=owned_scope(current_user) is None
# portfolio.py:640
user_id=None if allow_any_owner else user_id
```
فقط در `record_trade()` برای admin — به admin اجازه می‌دهد روی holding کاربر دیگری
معامله ثبت کند.

### ۲.۴ نقاط سازگاری FK

```
gold_holdings.id ←── gold_trades.holding_id (ondelete="SET NULL")
gold_trades.holding_id ←── NULL (وقتی holding حذف سخت می‌شود)
```

ستون `user_id` در holdings و trades **مستقل از هم** ست می‌شوند.
در خرید: هر دو از `current_user_id()` می‌آیند → سازگار.
در فروش admin با `allow_any_owner`: holding ممکن است `user_id="A"` داشته باشد
و trade جدید `user_id="admin"` → **ناسازگاری بالقوه**.

---

## ۳. شکاف‌های شناسایی‌شده

### G-1 (بالا): `user_id=NULL` در ردیف‌های legacy

**مشکل:** ردیف‌های `gold_holdings` و `gold_trades` با `user_id=NULL`:
- برای کاربران عادی **نامرئی** هستند (WHERE user_id='xyz' نتیجهٔ NULL را exclude می‌کند)
- برای admin **مرئی** هستند (بدون فیلتر)
- هیچ مسیری برای کاربر عادی برای ادعای مالکیت legacy ندارد

**اثر:**
- گزارش پورتفوی کاربر عادی holding‌های legacy را نشان نمی‌دهد حتی اگر متعلق به او باشند
- admin می‌تواند هم ردیف‌های NULL-owner و هم ردیف‌های user-owner را ببیند

### G-2 (متوسط): عدم تضمین NOT NULL در schema

**مشکل:** باگ‌های آینده می‌توانند به سادگی `user_id=None` ارسال کنند.
API layer اکنون آن را block می‌کند اما اگر endpoint جدید اشتباه نوشته شود،
شکاف silent ایجاد می‌شود.

### G-3 (متوسط): ناسازگاری user_id در trade-holding pair

**مشکل:** وقتی admin با `allow_any_owner=True` معامله ثبت می‌کند:
- `holding.user_id = "user123"`
- `trade.user_id = "admin"`

کاربر "user123" trade را در گزارش مالیاتی خود می‌بیند (کد `build_tax_summary`
trades را از holdings فیلتر می‌کند) اما:
- اگر کاربر "user123" درخواست trade list بدهد، این trade در آن می‌آید؟
- پاسخ: بله اگر `trade.user_id = "user123"` باشد. اما با `allow_any_owner` ممکن است
  `trade.user_id = "admin"` باشد → trade از لیست کاربر **حذف می‌شود**.

**نیاز به تأیید:** آیا admin در سناریوی واقعی از `allow_any_owner` استفاده می‌کند؟
اگر بله، آیا trade باید با `user_id` صاحب holding ثبت شود نه admin؟

### G-4 (پایین): `gold_portfolio_history` unique constraint

**مشکل:** `unique(user_id, as_of)` با `user_id=NULL` می‌تواند فقط **یک** ردیف per
`as_of` با NULL داشته باشد (در PostgreSQL `NULL = NULL` برای unique constraint کار
نمی‌کند — چندین NULL مجاز است). این باعث می‌شود legacy snapshots به درستی unique نباشند.

---

## ۴. مدل ownership پیشنهادی (برای Phase 1.5b)

### ۴.۱ اصل کلی

> **هر ردیف شخصی باید مالک مشخص داشته باشد.**
> admin فقط به‌عنوان ناظر (read-only) و با ابزار admin مجزا به ردیف‌های user دسترسی دارد.
> `user_id = NULL` فقط برای داده‌های عمومی/بازار مجاز است، نه داده‌های شخصی.

### ۴.۲ جدول مالکیت

| نوع داده | مالک | user_id | دسترسی admin |
|---------|------|---------|-------------|
| holdings/trades | کاربر مالک | NOT NULL | read-only via admin panel |
| alert rules/events | کاربر مالک | NOT NULL | read-only |
| DCA plans | کاربر مالک | NOT NULL | read-only |
| portfolio history | کاربر مالک | NOT NULL | read-only |
| snapshot cache | عمومی | — | full |
| fund NAV | عمومی | — | full |

### ۴.۳ تغییرات مورد نیاز (Phase 1.5b)

**مرحلهٔ ۱: Backfill (نیاز به تصمیم مالک)**

```sql
-- گزینهٔ A: assign به admin user (تصمیم مالک لازم است)
UPDATE gold_holdings SET user_id = '<ADMIN_USER_ID>' WHERE user_id IS NULL;
UPDATE gold_trades SET user_id = '<ADMIN_USER_ID>' WHERE user_id IS NULL;
-- ... همهٔ جداول شخصی
```

**مرحلهٔ ۲: NOT NULL constraint**

```sql
ALTER TABLE gold_holdings ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE gold_trades ALTER COLUMN user_id SET NOT NULL;
-- ... همهٔ جداول شخصی
```

**مرحلهٔ ۳: کد — رفع G-3 (allow_any_owner)**

```python
# portfolio.py:record_trade() — پیشنهاد
# اگر allow_any_owner=True، user_id را از holding بخوان نه از token
if allow_any_owner and holding_id is not None:
    h = await session.get(GoldHoldingModel, holding_id)
    effective_user_id = h.user_id  # trade با user_id صاحب holding ثبت شود
else:
    effective_user_id = user_id
```

**مرحلهٔ ۴: تضمین schema در `get_active_holding()`**

```python
# portfolio.py:103 — اضافه کردن assertion
if holding.user_id is None:
    logger.error("BUG: holding %d has NULL user_id — data integrity violation", holding_id)
    raise HoldingNotFoundError(f"holding {holding_id} has no owner")
```

---

## ۵. نقاط تصمیم (نیاز به تأیید مالک)

| # | سؤال | گزینه‌ها | پیش‌فرض پیشنهادی |
|---|------|---------|--------------|
| D1 | ردیف‌های legacy `user_id=NULL` به چه user_id‌ای backfill شوند؟ | (A) admin user (B) اولین کاربر ثبت‌شده (C) user_id اختصاصی "legacy" | گزینهٔ A — admin |
| D2 | آیا `allow_any_owner` در admin باید `trade.user_id` را از holding بگیرد؟ | (A) بله — trade با user_id صاحب holding (B) نه — trade با user_id admin ثبت شود | گزینهٔ A |
| D3 | آیا حذف سخت holding توسط admin مجاز بماند؟ | (A) بله با audit log (B) فقط soft-delete | گزینهٔ A با audit log |
| D4 | آیا admin می‌تواند holding/trade یک کاربر را به کاربر دیگر منتقل کند؟ | (A) بله با endpoint مخصوص (B) خیر | نیاز به تعریف product |

---

## ۶. فهرست endpoints — وضعیت ownership (audit)

| Endpoint | الگو | admin می‌بیند null? | ریسک |
|---------|------|-------------------|------|
| `GET /portfolio/holdings-grouped` | A | بله (کل پورتفوی) | پایین — طراحی عمدی |
| `GET /portfolio` | A | بله | پایین |
| `POST /portfolio/holdings` | — (insert) | user_id از token | پایین ✓ |
| `DELETE /portfolio/holdings/{id}` | B | بله (می‌تواند حذف کند) | متوسط — نیاز به audit log |
| `GET /portfolio/trades` | A | بله | پایین |
| `POST /portfolio/trade` | C | بله (allow_any_owner) | **متوسط G-3** |
| `GET /alerts/rules` | A | بله | پایین |
| `POST /alerts/rules` | — (insert) | user_id از token | پایین ✓ |
| `DELETE /alerts/rules/{id}` | B | بله | پایین |
| `GET /portfolio/tax` | A | بله | پایین |
| `GET /portfolio/value-history` | A | بله | پایین |
| `GET /portfolio/dca` | A | بله | پایین |

---

## ۷. ریسک‌های باقی‌مانده تا Phase 1.5b

| ریسک | احتمال | اثر | کاهش‌دهنده |
|------|--------|-----|-----------|
| ردیف legacy به کاربر غلط assign شود | متوسط | دادهٔ مالی غلط | تأیید دستی قبل از migration |
| migration در production fail شود | پایین | downtime | Test on copy first |
| admin به سهوی holding کاربر را ببیند | هم‌اکنون ✓ | — | مورد قبلاً حل‌شده — admin فقط read |

---

## ۸. اقدامات بعدی

**Phase 1.5a: کامل (این سند) — منتظر تأیید D1–D4**

**Phase 1.5b (فقط پس از تأیید D1–D4):**
1. [ ] Backfill migration برای `user_id=NULL` (جواب D1)
2. [ ] NOT NULL constraint migration
3. [ ] رفع G-3: `allow_any_owner` user_id correction (جواب D2)
4. [ ] `get_active_holding()` assertion برای user_id=NULL
5. [ ] تست: `needs_db` برای migration با GOLD_TEST_DATABASE_URL
6. [ ] commit با pathspec صریح

---

*فاز ۱.۵a کامل — هیچ تغییری در کد، migration یا داده اعمال نشده.*  
*منتظر پاسخ به سؤالات D1–D4 از مالک.*
