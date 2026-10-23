# Alerts Deep Dive (ویژه)

Sources: src/gold_desk/alert_engine.py:89-132, services/alert_service.py:203-288, app/alert_hub/repository.py:20-68, src/gold_desk/models.py:85-121

## معماری سه‌گانه (ناهمگن)
1. gold_desk engine: rule(edge: bubble/price/score/parity) + cooldown + event insert + telegram. بدون user_id روی rule/event.
2. AlertService (AlertModel): instrument_id OR symbol match، cooldown، history insert، channels console/sound/telegram/email.
3. alert_hub (SymbolAlertModel): upsert per (user,symbol)، deactivate نرم، snapshot جدا، cleanup snapshots غیرفعال.

## چرخه عمر
- Create: service OK (commit دارد :101)؛ hub upsert OK؛ gold seed فقط اگر جدول خالی :179.
- Toggle: service update enabled (flush بدون commit -> به commit بیرونی وابسته است :120)؛ hub is_active مشابه.
- Trigger: هر دو cooldown دارند؛ gold بر اساس last_fired_at روی rule؛ service بر اساس last_triggered روی alert.
- Delete: service حذف فیزیکی alert ولی history یتیم می‌ماند (بدون cascade دیده‌شده) -> ghost records؛ gold هیچ delete API ندارد -> ghost rules/events؛ hub فقط deactivate (نه حذف) + cleanup snapshots.
- Persistence: last_fired/last_triggered در DB ذخیره می‌شود پس reload/re-login حفظ می‌شود، مشروط بر commit موفق.

## ریسک‌های P0/P1
- P0-1 gold AlertRuleModel فاقد user_id است (models.py:85-102): نشت بین‌کاربری — کاربر A قانون کاربر B را می‌بیند/تریگر می‌کند. Patch: ستون user_id + فیلتر where در evaluate_rules.
- P0-2 Race double-fire: چک cooldown در حافظه سپس commit واحد (:106-130)؛ دو worker همزمان هر دو insert می‌کنند. همچنین service با flush (:284) بدون lock. Patch: select_for_update روی rule/alert یا unique constraint روی (rule_id, time_bucket) + on-conflict-do-nothing.
- P1-1 service update/delete فقط flush می‌کنند (نه commit) — اگر caller commit نکند toggle/delete گم می‌شود؛ تست reload باید commit صریح را assert کند.
- P1-2 یتیم‌ماندن history پس از delete (بدون FK cascade) و نبود delete در gold engine — نیاز به purge job + تست ghost-record.
- P1-3 Telegram failure نادیده گرفته می‌شود ولی event ثبت می‌شود (at-least-once)؛ باید delivered flag روی event هم ثبت شود مثل service.
- P2 float threshold/trigger (Float columns) — برای آستانه حساسیت 0.001 در eq/neq کافی است ولی برای قیمت ریالی Decimal توصیه می‌شود.

## چک‌لیست 15 آلرت پیشنهادی (قابل اجرای live)
Price>, Price<, %change, MA-cross x2, RSI x2, bubble_above/below, nav_bubble, score_above/below, parity_gap, signal TP/SL, cooldown-verify — سپس toggle/reload/trigger/delete برای هر کدام.
