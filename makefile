SERVICES ?= cli rag-core llm-gateway streamlit-ui evaluation-runner
ifeq ($(SERVICE),)
  TARGET_SERVICES := $(SERVICES)
else
  TARGET_SERVICES := $(SERVICE)
endif

COMPOSE_FILES := -f docker-compose.yml -f docker-compose.override.yml
HAS_NVIDIA := $(shell which nvidia-smi 2>/dev/null)
ifeq ($(HAS_NVIDIA),)
	GPU_STATUS := "CPU"
else
	COMPOSE_FILES += -f docker-compose.gpu.yml
	GPU_STATUS := "GPU"
endif

.PHONY: all up build ingest stop down-clean clean cli logs-rag logs-llm lint format ui uv-lock open prometheus grafana push

# --- MAIN ---
all: build up

build: uv-lock
	@echo "🔄 Building all services..."
	docker compose $(COMPOSE_FILES) build

up:
	@echo "========================================================"
	@echo "🚀 Starting all services with $(GPU_STATUS) in detached mode..."
	@echo "========================================================"
	docker compose $(COMPOSE_FILES) up -d

down:
	docker compose down
	@echo "🛑 All services have been stopped."

re: down up

rebuild: down all

ingest:
	@echo "🔄 Ingesting new documents into RAG..."
	curl -X POST http://localhost/api/ingest 

cli:
	@echo "🚀 Accessing API service CLI..."
	@docker compose exec -it cli python main.py

ui:
	@$(MAKE) --no-print-directory open URL=http://localhost/


#--- DEV ---
down-clean:
	docker compose down -v
	@echo "🛑 All services have been stopped and volumes removed."

clean:
	@for service in $(TARGET_SERVICES); do \
		rm -rf src/$$service/__pycache__; \
		rm -rf src/$$service/.ruff_cache; \
		rm -rf src/$$service/.pytest_cache; \
		rm -rf src/$$service/.venv; \
	done

docker-clean:
	docker system prune -a --volumes -f

prometheus:
	@$(MAKE) --no-print-directory open URL=http://localhost/prometheus/

grafana:
	@$(MAKE) --no-print-directory open URL=http://localhost/grafana/

minio:
	@$(MAKE) --no-print-directory open URL=http://localhost/minio/

pgadmin:
	@$(MAKE) --no-print-directory open URL=http://localhost/pgadmin/

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
