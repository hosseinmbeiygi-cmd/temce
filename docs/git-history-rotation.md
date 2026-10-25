# Git History Secret Rotation

## Context
Before this change, two plaintext credentials were committed to git history:
- `<masked-from-history>` (PostgreSQL password)
- `<masked-from-history>` (Redis password)

The current tree is clean (gitleaks passes), but the secrets still live in
older commits and are reachable by anyone with read access to the history.

> **تصحیح ۲۰۲۶-۱۰-۲۴ (دستیار ۳ / S3):** جملهٔ بالا برای امروز این repo **درست نیست**.
> همین دو مقدار هنوز در درخت کاری plaintextند:
> `docker-compose.decision-engine.yml:49,73,74,76` و
> `k8s/decision-engine-secret.yaml:19,22` (کامنت‌های آن manifest) و نسخهٔ base64‌شان
> در خط‌های ۲۰ و ۲۳ همان فایل. ضمناً خودِ این سند تا پیش از این تاریخ، هر دو مقدار را
> در خط‌های ۵، ۶، ۳۱، ۳۲ و ۴۵ دوباره چاپ کرده بود که **۶ occurrence ماسک شد**
> (`<masked-from-history>`). یعنی فایل‌های track‌شدهٔ امروز هم دوباره باید scrub شوند،
> نه فقط تاریخچه. جزئیات و مالکیت رفع: `docs/security/secret_scan_report.md §۲-الف`.
> مقادیر را این‌جا نمی‌نویسم (قاعدهٔ ۵؛ اسکنر و `git log` مرجع دیدن مقدارند).

## ⚠️ Risk
This is a **force-push operation** that rewrites the public commit graph.
All contributors must re-clone or rebase. CI caches keyed on commit SHA
will need to be invalidated. **Coordinate with the team before running.**

## Procedure

### 1. Install BFG (one-time)
```bash
brew install bfg        # macOS
# or download: https://rtyley.github.io/bfg-repo-cleaner/
```

### 2. Backup
```bash
cp -R .git .git.backup.$(date +%Y%m%d)
```

### 3. Create a `secrets.txt` file with the strings to scrub

**خارج از repo** بسازید (مثلاً `~/secrets.txt`) تا خودِ سندِ پاک‌سازی دوباره محل چاپ
credential نشود — دقیقاً همان اشتباهی که این فایل مرتکب شده بود. یک مقدار در هر خط،
برداشت از `git log` یا secret manager (نه از یک سند track‌شده):

```bash
${EDITOR:-nano} "$HOME/secrets.txt"   # دو خط: رمز PostgreSQL، سپس رمز Redis
chmod 600 "$HOME/secrets.txt"
```

### 4. Run BFG
```bash
bfg --replace-text "$HOME/secrets.txt" --no-blob-protection
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 5. Verify
```bash
# Should report no matches. (grep -F -f تا مقدار در فرمان یا در repo تکرار نشود)
git log --all -p | grep -F -f "$HOME/secrets.txt" || echo "CLEAN"
```

### 6. Force-push
```bash
# Coordinate first. Notify team in #deploys channel.
git push --force --all
git push --force --tags
```

### 7. Invalidate downstream caches
- GitHub: protected branch rules already prevent rewriting, you may need
  to temporarily disable them.
- Codecov: invalidates automatically on new SHAs.
- Container registries: re-push images with new SHAs.
- Anyone with local clones: re-clone or `git pull --rebase` (after fetch).

### 8. **Rotate the actual secrets**
The history rewrite does not invalidate the live credentials. Generate new
strong passwords in `docker-compose.decision-engine.yml`'s `.env`, and in
any deployment that uses the old values.

## Why not just rewrite and skip rotation?
Stolen credentials are not "returned" by history rewrites. Anyone who
fetched the repo before the rewrite still has the secrets. Treat the
old values as compromised and rotate.
