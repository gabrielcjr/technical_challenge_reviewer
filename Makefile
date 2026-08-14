.PHONY: build up down logs ps shell django-shell evaluator-shell migrate worker-logs test test-django test-evaluator restart rebuild run-check-flake8 run-check-black run-fix-black run-check-isort run-fix-isort run-fix-autoflake run-check-linters run-fix-linters

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
	@echo "Django Backend API: http://localhost:$${API_PORT:-8080}"
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

evaluator-shell:
	docker compose exec evaluator sh

migrate:
	docker compose exec django python manage.py migrate --noinput

makemigrations:
	docker compose exec django python manage.py makemigrations

worker-logs:
	docker compose logs -f celery-worker

test-django:
	docker compose exec django python manage.py test

test-evaluator:
	docker compose exec evaluator pytest -v

test:
	$(MAKE) test-django
	$(MAKE) test-evaluator

run-check-flake8:
	flake8 . --config .flake8 --count --show-source --statistics

run-check-black:
	black --check . --config pyproject.toml

run-fix-black:
	black . --config pyproject.toml

run-check-isort:
	isort . --check-only --settings-file pyproject.toml

run-fix-isort:
	isort . --settings-file pyproject.toml

run-fix-autoflake:
	autoflake --remove-all-unused-imports --recursive --in-place . --exclude=apps.py,.venv,.docker

run-check-linters:
	make run-check-flake8
	make run-check-black
	make run-check-isort

run-fix-linters:
	make run-fix-black
	make run-fix-isort
	make run-fix-autoflake

restart:
	docker compose restart

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d
