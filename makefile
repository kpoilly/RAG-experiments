COMPOSE_FILES := -f docker-compose.yml -f docker-compose.override.yml

HAS_NVIDIA := $(shell which nvidia-smi 2>/dev/null)
ifeq ($(HAS_NVIDIA),)
	GPU_STATUS := "CPU"
else
	COMPOSE_FILES += -f docker-compose.gpu.yml
	GPU_STATUS := "GPU"
endif

SERVICES_FOLDERS := api rag_core llm_gateway
CONFIG_FILES := pyproject.toml

.PHONY: all up build ingest stop clean start-chat

# --- GENERIC COMMANDS ---
all: build up start-chat

up:
	@echo "========================================================"
	@echo "Starting with: $(GPU_STATUS)"
	@echo "========================================================"
	docker compose $(COMPOSE_FILES) up -d

build: sync-configs
	@echo "========================================================"
	@echo "Building $(GPU_STATUS) version"
	@echo "========================================================"
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

clean:
	docker compose down -v

start-chat:
	docker compose exec -it api python main.py


#--- LOGS ---
logs-rag:
	docker compose logs rag-core -f

logs-llm:
	docker compose logs llm-gateway -f

# --- QUALITY & TESTING COMMANDS ---
lint:
	@echo "===== CHECKING CODE QUALITY ====="
	docker compose run --rm api sh -c "ruff check /app && black --check /app"
	docker compose run --rm rag-core sh -c "ruff check /app && black --check /app"
	docker compose run --rm llm-gateway sh -c "ruff check /app && black --check /app"

format:
	@echo "===== FORMATTING CODE ====="
	docker compose run --rm api sh -c "ruff check /app --fix; black /app"
	docker compose run --rm rag-core sh -c "ruff check /app --fix; black /app"
	docker compose run --rm llm-gateway sh -c "ruff check /app --fix; black /app"