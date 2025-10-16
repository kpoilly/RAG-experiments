HAS_NVIDIA := $(shell which nvidia-smi 2>/dev/null)
ifeq ($(HAS_NVIDIA),)
	COMPOSE_FILE := -f docker-compose.yml
	GPU_STATUS := "CPU"
else
	COMPOSE_FILE := -f docker-compose.gpu.yml
	GPU_STATUS := "GPU"
endif

.PHONY: all build stop start-chat

all: build
	@echo "========================================================"
	@echo "Starting with: $(GPU_STATUS)"
	@echo "========================================================"
	docker compose $(COMPOSE_FILES) up -d

build:
	@echo "========================================================"
	@echo "Building $(GPU_STATUS) version"
	@echo "================================================"
	docker compose $(COMPOSE_FILES) build

stop:
	docker compose down

start-chat:
	docker compose exec -it api python main.py
	