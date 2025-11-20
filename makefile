SERVICES ?= cli rag-core llm-gateway streamlit-ui evaluation-runner
ifeq ($(SERVICE),)
  TARGET_SERVICES := $(SERVICES)
else
  TARGET_SERVICES := $(SERVICE)
endif

.PHONY: all build up down clean-data re rebuild ingest eval cli ui \
prometheus grafana minio pgadmin dev clean-folders docker-clean \
open uv-lock logs-rag logs-llm logs-eval lint format push


# --- BUILDING ---
all: build up

build: uv-lock
	@echo "🔄 Building all services..."
	docker compose -f docker-compose.yml build

up:
	@echo "🚀 Starting all services..."
	docker compose -f docker-compose.yml up -d
	@echo "✨ All services have been started. Access UI with 'make ui' or at http://localhost/"

down:
	docker compose down
	@echo "🛑 All services have been stopped."

clean-data:
	docker compose down -v
	@echo "🛑 All services have been stopped and volumes removed."

re: down up

rebuild: down all


# --- INTERACTIONS ---
register:
	@curl -X POST "http://localhost/api/auth/register" \
	-H "Content-Type: application/json" \
	-d '{"email": "admin@admin.com", "password": "admin"}'

login:
	@curl -X POST "http://localhost/api/auth/token" \
	-H "Content-Type: application/x-www-form-urlencoded" \
	-d "username=admin@admin.com&password=admin"

ingest:
	@echo "🔄 Ingesting new documents into RAG..."
	curl -X POST http://localhost/api/documents/ingest 

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
SCRIPTS_VENV := scripts/.venv
SCRIPTS_PYTHON := $(SCRIPTS_VENV)/bin/python

dev: uv-lock
	docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d

bootstrap: $(SCRIPTS_VENV)/touchfile
	@echo "--- Initializing project (secrets, auth token) ---"
	@$(SCRIPTS_PYTHON) scripts/bootstrap.py

$(SCRIPTS_VENV)/touchfile: scripts/requirements.txt
	@echo "--- Setting up virtual environment for scripts... ---"
	@if ! command -v uv > /dev/null; then \
		echo "uv not found, installing..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	@uv venv $(SCRIPTS_VENV) --python 3.12 --clear -q
	@uv pip install -p $(SCRIPTS_VENV) -r scripts/requirements.txt -q
	@touch $(SCRIPTS_VENV)/touchfile

clean-bootstrap:
	@echo "--- Cleaning bootstrap artifacts ---"
	@rm -rf $(SCRIPTS_VENV)

clean-folders:
	@sudo find . -type d -name "__pycache__" -exec rm -rf {} +
	@sudo find . -type d -name ".ruff_cache" -exec rm -rf {} +

docker-nuke: clean-data
	docker stop $(docker ps -aq) 2>/dev/null; docker rm $(docker ps -aq) 2>/dev/null; docker system prune --all --volumes --force

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

generate-encrypt:
	python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"


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
push: format clean-folders
	git add .
	git commit -m "$(MSG)"
	git push origin main
