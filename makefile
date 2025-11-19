SERVICES ?= cli rag-core llm-gateway streamlit-ui evaluation-runner
ifeq ($(SERVICE),)
  TARGET_SERVICES := $(SERVICES)
else
  TARGET_SERVICES := $(SERVICE)
endif

.PHONY: all build up down clean-data re rebuild ingest eval cli ui \
prometheus grafana minio pgadmin dev clean-folders docker-clean \
open uv-lock logs-rag logs-llm logs-eval lint format push


# --- MAIN ---
all: build up

build: uv-lock
	@echo "🔄 Building all services..."
	docker compose -f docker-compose.yml build

up:
	docker compose -f docker-compose.yml up -d

down:
	docker compose down
	@echo "🛑 All services have been stopped."

clean-data:
	docker compose down -v
	@echo "🛑 All services have been stopped and volumes removed."

re: down up

rebuild: down all

ingest:
	@echo "🔄 Ingesting new documents into RAG..."
	curl -X POST http://localhost/api/ingest 

eval:
	@echo "📝 Running a RAGAS evaluation..."
	@docker compose exec -it evaluation-scheduler curl -s -X POST http://evaluation-runner:8004/evaluate

cli:
	@echo "🚀 Accessing API service CLI..."
	@docker compose exec -it cli python main.py

ui:
	@$(MAKE) --no-print-directory open URL=http://localhost/

prometheus:
	@$(MAKE) --no-print-directory open URL=http://localhost/prometheus/

grafana:
	@$(MAKE) --no-print-directory open URL=http://localhost/grafana/

minio:
	@$(MAKE) --no-print-directory open URL=http://localhost/minio/

pgadmin:
	@$(MAKE) --no-print-directory open URL=http://localhost/pgadmin/

#--- DEV ---
dev:
	docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d

clean-folders:
	@for service in $(TARGET_SERVICES); do \
		rm -rf src/$$service/__pycache__; \
		rm -rf src/$$service/.ruff_cache; \
		rm -rf src/$$service/.pytest_cache; \
		rm -rf src/$$service/.venv; \
	done

docker-clean: clean-data
	docker system prune -a --volumes -f

open:
	@if [ -z "$(URL)" ]; then \
		echo "🔴 Error: URL argument is missing."; \
		echo "Usage: make open URL=<your_url>"; \
		exit 1; \
	fi

	@echo "🌍 Opening $(URL) in browser..."
	@sh -c ' \
			URL_TO_OPEN="$(URL)"; \
			case "`uname -s`" in \
				Linux*) \
					if grep -q -i Microsoft /proc/version; then \
						explorer.exe "$$URL_TO_OPEN" || true; \
					else \
						xdg-open "$$URL_TO_OPEN" || true; \
					fi \
					;; \
				Darwin*) \
					open "$$URL_TO_OPEN" || true; \
					;; \
				CYGWIN*|MINGW*|MSYS*) \
					start "$$URL_TO_OPEN" || true; \
					;; \
				*) \
					echo "Could not detect OS, please open "$$URL_TO_OPEN" manually."; \
					;; \
			esac \
		'

uv-lock:
	@for service in $(TARGET_SERVICES); do \
		uv lock --directory src/$$service/; \
	done


#--- LOGS ---
logs-rag:
	docker compose logs rag-core -f

logs-llm:
	docker compose logs llm-gateway -f

logs-eval:
	docker compose logs evaluation-runner -f


# --- QUALITY & TESTING ---
lint:
	@echo "===== CHECKING CODE QUALITY FOR $(TARGET_SERVICES) ====="
	@for service in $(TARGET_SERVICES); do \
		echo "--- Linting $$service ---"; \
		echo "Building linter image for $$service..."; \
		docker build \
			--target linter \
			--tag $$service-linter \
			./src/$$service; \
		echo "Running checks in a temporary container..."; \
		docker run --rm $$service-linter sh -c "ruff check . && black --check ."; \
	done

format:
	@echo "===== FORMATTING CODE FOR $(TARGET_SERVICES) ====="
	@for service in $(TARGET_SERVICES); do \
		echo "--- Formatting $$service ---"; \
		echo "Building linter image for $$service..."; \
		docker build \
			--target linter \
			--tag $$service-linter \
			./src/$$service; \
		echo "Applying fixes in a temporary container..."; \
		docker run --rm \
			-v ./src/$$service:/app \
			$$service-linter sh -c "ruff check . --fix && black ."; \
	done


# --- GIT ---
push: format
	git add .
	git commit -m "$(MSG)"
	git push origin main
