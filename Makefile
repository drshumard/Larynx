# Larynx TTS - Makefile

.PHONY: help build up down logs restart clean dev prod

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images
	docker compose build

build-no-cache: ## Build all Docker images without cache
	docker compose build --no-cache

up: ## Start all services in detached mode
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Follow logs from all services
	docker compose logs -f

logs-backend: ## Follow backend logs
	docker compose logs -f backend

logs-frontend: ## Follow frontend logs
	docker compose logs -f frontend

dev: ## Start development environment
	docker compose up -d mongodb
	@echo "MongoDB started. Run backend and frontend locally."

prod: ## Start production environment with nginx
	docker compose --profile production up -d

clean: ## Stop services and remove volumes
	docker compose down -v
	@echo "All data has been removed."

status: ## Show status of all services
	docker compose ps

shell-backend: ## Open shell in backend container
	docker compose exec backend bash

shell-mongo: ## Open MongoDB shell
	docker compose exec mongodb mongosh

health: ## Check health of all services
	@echo "Backend:"
	@curl -s http://localhost:8001/api/health | python3 -m json.tool || echo "Backend not responding"
	@echo "\nFrontend:"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 && echo " OK" || echo "Frontend not responding"

test-api: ## Test API endpoints
	@echo "Testing health endpoint..."
	curl -s http://localhost:8001/api/health | python3 -m json.tool
	@echo "\nTesting settings endpoint..."
	curl -s http://localhost:8001/api/settings | python3 -m json.tool
	@echo "\nTesting jobs endpoint..."
	curl -s http://localhost:8001/api/jobs | python3 -m json.tool
