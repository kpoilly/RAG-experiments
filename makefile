SERVICES ?= api rag-core llm-gateway
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

SERVICES_FOLDERS := rag_core llm_gateway api
CONFIG_FILES := pyproject.toml

.PHONY: all up build sync-configs ingest stop down-clean clean start-chat logs-rag logs-llm lint format

# --- MAIN ---
all: build up start-chat

up:
	@echo "========================================================"
	@echo "Starting with: $(GPU_STATUS)"
	@echo "========================================================"
	docker compose $(COMPOSE_FILES) up -d

build: sync-configs
	docker compose $(COMPOSE_FILES) build

sync-configs:
	@for service in $(SERVICES_FOLDERS); do \
		for config_file in $(CONFIG_FILES); do \
			cp $$config_file src/$$service/$$config_file; \
		done; \
	done

ingest:
	@echo "Ingesting new documents..."
	curl -X POST http://localhost:8001/ingest 

down:
	docker compose down

down-clean:
	docker compose down -v

start-chat:
	docker compose exec -it api python main.py

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