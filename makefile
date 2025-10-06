all:
	docker compose up -d --build

start-chat:
	docker compose exec -it api python main.py