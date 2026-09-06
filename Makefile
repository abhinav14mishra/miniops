up:
	docker compose up --build

down:
	docker compose down

test:
	docker compose run --rm api pytest -q

logs:
	docker compose logs -f
