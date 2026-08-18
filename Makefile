.PHONY: help up down dev check lint typecheck test test-arch install install-frontend

# Exibe comandos disponíveis
help:
	@echo "Comandos disponíveis:"
	@echo "  make up              Sobe banco + adminer + API via Docker Compose"
	@echo "  make down            Para todos os containers"
	@echo "  make dev             Roda backend (uvicorn) e frontend (vite) em modo dev"
	@echo "  make check           Roda todos os checks: lint, tipos, testes, arquitetura"
	@echo "  make lint            ruff check no backend"
	@echo "  make typecheck       mypy strict no backend"
	@echo "  make test            pytest"
	@echo "  make test-arch       Teste de arquitetura (bloqueia imports Yelum fora de adapters/)"
	@echo "  make install         Instala dependências do backend"
	@echo "  make install-frontend Instala dependências do frontend"

# --- Docker ---

up:
	docker compose up --build

down:
	docker compose down

# --- Dev local (sem Docker para o app) ---

dev:
	@echo "Iniciando backend e frontend em paralelo..."
	@(cd backend && uvicorn app.main:app --reload --port 8000) &
	@(cd frontend && npm run dev) &
	@wait

# --- Quality gates (roda no CI e localmente via 'make check') ---

check: lint typecheck test test-arch
	@echo "✓ Todos os checks passaram."

lint:
	cd backend && ruff check .
	cd backend && ruff format --check .

typecheck:
	cd backend && mypy app

test:
	cd backend && pytest -v

test-arch:
	@echo "Verificando isolamento de imports da Yelum..."
	@if grep -ri "yelum\|BrokerProposalNumber\|CoverageCode\|CommercialProductCode" \
		backend/app/domain backend/app/api backend/app/infra backend/app/main.py \
		2>/dev/null | grep -v "^Binary"; then \
		echo "ERRO: referência a Yelum encontrada fora de adapters/yelum/"; \
		exit 1; \
	fi
	@echo "✓ Isolamento OK."

# --- Instalação ---

install:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install
