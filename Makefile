.PHONY: install lint typecheck test dev dev-all api worker admin docker-up docker-build backup prod-check clean

# ── Dependencies ──────────────────
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# ── Quality ───────────────────────
lint:
	ruff check . --fix

typecheck:
	mypy apps core domain services --ignore-missing-imports || true

test:
	pytest tests/unit -v --tb=short --timeout=60

test-all:
	pytest tests/ -v --tb=short --timeout=120

# ── Local Development ─────────────
dev:
	uvicorn apps.api.app:app --reload --host 0.0.0.0 --port 8000

api:
	uvicorn apps.api.app:app --host 0.0.0.0 --port 8000

admin:
	uvicorn apps.admin.app:admin_app --host 0.0.0.0 --port 8001

worker:
	python -m jobs.worker

# ── Run All Dev Servers ───────────
dev-all:
	@powershell -ExecutionPolicy Bypass -File run.ps1

# ── Docker ────────────────────────
docker-up:
	docker compose up --build -d

docker-build:
	docker compose build

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f

docker-prod:
	docker stack deploy -c docker-compose.yml -c docker-compose.production.yml market

# ── Database ──────────────────────
backup:
	python scripts/backup_postgres.py

backup-list:
	python scripts/backup_postgres.py --list

restore:
	python scripts/backup_postgres.py --restore $(file)

migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(name)"

# ── Production check ──────────────
prod-check:
	python -c "from core.config import settings; settings.validate_production()"

# ── Cleanup ───────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .coverage coverage.xml

# ── Help ──────────────────────────
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development:"
	@echo "  install      Install all dependencies"
	@echo "  lint         Run ruff linter"
	@echo "  typecheck    Run mypy type checker"
	@echo "  test         Run unit tests"
	@echo "  dev          Start API with hot reload"
	@echo "  dev-all      Start backend + frontend together"
	@echo "  api          Start API server"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up    Build and start all services"
	@echo "  docker-down  Stop and remove volumes"
	@echo ""
	@echo "Database:"
	@echo "  backup       Create PostgreSQL backup"
	@echo "  migrate      Run pending migrations"
	@echo ""
	@echo "Production:"
	@echo "  prod-check   Validate production configuration"
