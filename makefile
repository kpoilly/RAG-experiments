SERVICES ?= cli rag-core llm-gateway streamlit-ui
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

SERVICES_FOLDERS := rag_core llm_gateway cli streamlit_ui
CONFIG_FILES := pyproject.toml

.PHONY: all up build sync-configs ingest stop down-clean clean cli logs-rag logs-llm lint format ui

# --- MAIN ---
all: build up ui

up:
	@echo "========================================================"
	@echo "🚀 Starting all services with $(GPU_STATUS) in detached mode..."
	@echo "========================================================"
	docker compose $(COMPOSE_FILES) up -d

build: sync-configs
	@echo "🚀 Building all services..."
	docker compose $(COMPOSE_FILES) build

ingest:
	@echo "🔄 Ingesting new documents into RAG..."
	curl -X POST http://localhost:8001/ingest 

down:
	docker compose down
	@echo "🛑 All services have been stopped."

cli:
	@echo "🚀 Accessing API service CLI..."
	@docker compose exec -it cli python main.py

ui:
	@echo "🌍 Opening Streamlit UI in browser at http://localhost..."
	@sh -c ' \
			case "`uname -s`" in \
				Linux*) \
					if grep -q -i Microsoft /proc/version; then \
						explorer.exe http://localhost || true; \
					else \
						xdg-open http://localhost || true; \
					fi \
					;; \
				Darwin*) \
					open http://localhost || true; \
					;; \
				CYGWIN*|MINGW*|MSYS*) \
					start http://localhost || true; \
					;; \
				*) \
					echo "Could not detect OS, please open http://localhost manually."; \
					;; \
			esac \
		'


#--- DEV ---
sync-configs:
	@for service in $(SERVICES_FOLDERS); do \
		for config_file in $(CONFIG_FILES); do \
			cp $$config_file src/$$service/$$config_file; \
		done; \
	done

down-clean:
	docker compose down -v
	@echo "🛑 All services have been stopped and volumes removed."

docker-clean:
	docker system prune -a --volumes -f

clean:
	@for service in $(SERVICES_FOLDERS); do \
		rm -f src/$$service/pyproject.toml; \
		rm -rf src/$$service/__pycache__; \
		rm -rf src/$$service/.ruff_cache; \
		rm -rf src/$$service/.pytest_cache; \
	done


#--- LOGS ---
logs-rag:
	docker compose logs rag-core -f

logs-llm:
	docker compose logs llm-gateway -f


# --- QUALITY & TESTING ---
lint:
	@echo "===== CHECKING CODE QUALITY FOR $(TARGET_SERVICES) ====="
	@for service in $(TARGET_SERVICES); do \
		echo "--- Linting $$service ---"; \
		docker compose run --rm $$service sh -c "ruff check /app/ && black --check /app/"; \
	done

format:
	@echo "===== FORMATTING CODE FOR $(TARGET_SERVICES) ====="
	@for service in $(TARGET_SERVICES); do \
		echo "--- Formatting $$service ---"; \
		docker compose run --rm $$service sh -c "ruff check /app/ --fix; black /app/"; \
	done


# --- GIT ---
push: format
	git add .
	git commit -m "$(MSG)"
	git push origin main
