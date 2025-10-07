all:
	docker compose up -d --build

stop:
	docker compose down

start-chat:
	docker compose exec -it api python main.py