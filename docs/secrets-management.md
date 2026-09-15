# Secret Management Guide

## Policy
- No plaintext secret is ever committed to git.
- All secrets flow from: environment variables → compose/K8s → container env.
- Local dev: copy `.env.example` to `.env` (gitignored) and fill real values.
- CI: GitHub Actions Encrypted Secrets (Settings → Secrets).
- Production: external store (see below).

## Docker Compose
Use `${VAR:?error}` form. Example (`docker-compose.decision-engine.yml`):
```yaml
environment:
  - POSTGRES_PASSWORD=${DE_POSTGRES_PASSWORD:?DE_POSTGRES_PASSWORD must be set}
```
If the variable is unset, compose aborts with a clear error.

## Kubernetes

### Option A: Sealed Secrets (GitOps-friendly)
```bash
# One-time per cluster
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml

# Encrypt a plain secret
kubectl create secret generic decision-engine-secret \
  --from-literal=DATABASE_PASSWORD='real-password' \
  --from-literal=REDIS_PASSWORD='real-redis-pass' \
  --from-literal=SECRET_KEY='random-32-chars' \
  --dry-run=client -o yaml | \
  kubeseal --format yaml > k8s/decision-engine-sealed.yaml

# Commit only the sealed version; the controller decrypts in-cluster.
git add k8s/decision-engine-sealed.yaml
git commit -m "chore: rotate decision-engine sealed secret"
kubectl apply -f k8s/decision-engine-sealed.yaml
```

### Option B: External Secrets Operator
```bash
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
```
Define `SecretStore` (Vault / AWS SM / GCP SM) + `ExternalSecret` that mirrors into the same `Secret` name the deployment references. Delete `k8s/decision-engine-secret.yaml` from git once ESO is in place.

### Rotation
Rotate every 90 days. Procedure:
1. Generate new value in the external store (Vault write / SM update-secret).
2. ESO / Sealed Secrets resyncs the K8s Secret.
3. Roll the deployment: `kubectl rollout restart deployment/decision-engine`.
4. Old value remains valid until pods pick up the new Secret.

## Local Dev
```bash
cp .env.example .env
# edit .env — values are loaded by compose automatically
docker compose -f docker-compose.decision-engine.yml up -d
```

## Pre-commit
A `gitleaks` pre-commit hook blocks any commit that adds a secret. To bypass (rare, justified), set `GITLEAKS_ALLOW_REDACT=1` in your shell.
