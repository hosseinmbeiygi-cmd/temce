# Git History Secret Rotation

## Context
Before this change, two plaintext credentials were committed to git history:
- `decision_pass_456` (PostgreSQL password)
- `de_redis_pass_789` (Redis password)

The current tree is clean (gitleaks passes), but the secrets still live in
older commits and are reachable by anyone with read access to the history.

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
```text
decision_pass_456
de_redis_pass_789
```

### 4. Run BFG
```bash
bfg --replace-text secrets.txt --no-blob-protection
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 5. Verify
```bash
# Should report no matches.
git log --all -p | grep -E "decision_pass_456|de_redis_pass_789" || echo "CLEAN"
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
