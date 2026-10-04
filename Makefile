# ============================================================
# Marcbantu Africa — Makefile
# Convenience targets for common workflows.
# ============================================================

.PHONY: help setup dev test lint deploy backup reset seed clean

# ---------- Help (default) ----------
help:
	@echo ""
	@echo "Marcbantu Africa — Available Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  Development:"
	@echo "    make dev          Start local dev servers"
	@echo "    make backend      Start only backend dev"
	@echo "    make frontend     Start only frontend dev"
	@echo ""
	@echo "  Database:"
	@echo "    make setup        Create DB, run migrations, load seeds"
	@echo "    make seed         Load seed data only"
	@echo "    make reset        ⚠ Wipe and rebuild DB (local)"
	@echo "    make reset-prod   ⚠ Wipe and rebuild DB (production)"
	@echo "    make backup       Backup remote database"
	@echo ""
	@echo "  Testing:"
	@echo "    make test         Run all tests"
	@echo "    make test-cov     Run tests with coverage"
	@echo "    make lint         Run linters"
	@echo ""
	@echo "  Deployment:"
	@echo "    make deploy       Deploy backend + frontend"
	@echo "    make deploy-back  Deploy backend only"
	@echo "    make deploy-front Deploy frontend only"
	@echo "    make staging      Deploy to staging"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make logs         Tail Worker logs"
	@echo "    make clean        Remove build artifacts"
	@echo ""

# ---------- Development ----------
dev:
	@echo "Starting dev servers (Ctrl+C to stop both)..."
	@$(MAKE) -j2 backend frontend

backend:
	@wrangler dev

frontend:
	@cd frontend && python3 -m http.server 8788

# ---------- Database ----------
setup:
	@bash backend/scripts/db_setup.sh

setup-prod:
	@bash backend/scripts/db_setup.sh --remote

seed:
	@bash backend/scripts/db_seed.sh

seed-prod:
	@bash backend/scripts/db_seed.sh --remote

reset:
	@bash backend/scripts/db_reset.sh

reset-prod:
	@bash backend/scripts/db_reset.sh --remote

backup:
	@bash backend/scripts/backup.sh

backup-local:
	@bash backend/scripts/backup.sh --local

# ---------- Testing ----------
test:
	@bash backend/scripts/test.sh

test-cov:
	@bash backend/scripts/test.sh --cov

lint:
	@bash backend/scripts/test.sh --lint

# ---------- Deployment ----------
deploy:
	@bash backend/scripts/deploy.sh

deploy-back:
	@bash backend/scripts/deploy.sh --backend

deploy-front:
	@bash backend/scripts/deploy.sh --frontend

staging:
	@bash backend/scripts/deploy.sh --staging

dry-run:
	@bash backend/scripts/deploy.sh --dry-run

# ---------- Maintenance ----------
logs:
	@wrangler tail

clean:
	@rm -rf .wrangler node_modules backend/htmlcov backend/**/__pycache__ 2>/dev/null || true
	@echo "Cleaned build artifacts"
