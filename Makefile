.PHONY: build up down logs ps shell django-shell python-shell migrate worker-logs test test-django test-python restart rebuild

include .env
export

build:
	docker compose build

up:
	docker compose up -d
	@echo "Waiting for DB..."
	@sleep 3
	@echo "Services:"
	docker compose ps
	@echo ""
	@echo "Django Backend API: http://localhost:$${SYMFONY_PORT:-8080}"
	@echo "Python Evaluator: http://localhost:$${EVALUATOR_PORT:-8001}/docs"
	@echo "Postgres: localhost:$${POSTGRES_PORT:-5432}"

down:
	docker compose down

down-v:
	docker compose down -v

logs:
	docker compose logs -f

ps:
	docker compose ps

django-shell:
	docker compose exec django sh

python-shell:
	docker compose exec python-evaluator sh

migrate:
	docker compose exec django python manage.py migrate --noinput

makemigrations:
	docker compose exec django python manage.py makemigrations

worker-logs:
	docker compose logs -f django-worker

test-django:
	docker compose exec django python manage.py test

test-python:
	docker compose exec python-evaluator pytest -v

test:
	$(MAKE) test-django
	$(MAKE) test-python

restart:
	docker compose restart

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d
