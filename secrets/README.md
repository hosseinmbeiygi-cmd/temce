# secrets/

This directory holds Docker secrets consumed by `docker-compose.production.yml`.
It is **not tracked by git** (see `.gitignore`).

Create each file before running `docker compose -f docker-compose.production.yml up`:

| File | Contents |
|------|----------|
| `postgres_password.txt` | PostgreSQL password for the `market` user |
| `secret_key.txt` | 64-byte random string — `openssl rand -hex 32` |
| `api_key.txt` | Internal API key for service-to-service calls |

```bash
install -m 700 -d secrets
openssl rand -hex 32 > secrets/postgres_password.txt
openssl rand -hex 32 > secrets/secret_key.txt
openssl rand -hex 32 > secrets/api_key.txt
chmod 600 secrets/*.txt
```

CFG-02: without these files `docker stack deploy` will refuse to start because
the `postgres_password`, `secret_key`, and `api_key` secrets are declared with
`file:` references in docker-compose.production.yml.
