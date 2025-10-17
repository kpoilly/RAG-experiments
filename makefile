HAS_NVIDIA := $(shell which nvidia-smi 2>/dev/null)
ifeq ($(HAS_NVIDIA),)
	COMPOSE_FILE := -f docker-compose.yml
	GPU_STATUS := "CPU"
else
	COMPOSE_FILE := -f docker-compose.gpu.yml
	GPU_STATUS := "GPU"
endif

.PHONY: all up build ingest stop clean start-chat

all: build up start-chat

up:
	@echo "========================================================"
	@echo "Starting with: $(GPU_STATUS)"
	@echo "========================================================"
	docker compose $(COMPOSE_FILES) up -d

build:
	@echo "========================================================"
	@echo "Building $(GPU_STATUS) version"
	@echo "================================================"
	docker compose $(COMPOSE_FILES) build

ingest:
	@echo "Ingesting new documents..."
	curl -X POST http://localhost:8001/ingest 

stop:
	docker compose down

clean:
	docker compose down -v

start-chat:
	docker compose exec -it api python main.py
	