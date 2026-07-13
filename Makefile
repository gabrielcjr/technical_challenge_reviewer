.PHONY: build up down logs ps shell php-shell python-shell install migrate fixtures worker-logs test

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
	@echo "Symfony: http://localhost:$${SYMFONY_PORT:-8080}"
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

php-shell:
	docker compose exec php sh

python-shell:
	docker compose exec python-evaluator sh

install:
	docker compose exec php composer install

migrate:
	docker compose exec php php bin/console doctrine:migrations:migrate --no-interaction

migrations-diff:
	docker compose exec php php bin/console doctrine:migrations:diff

fixtures:
	docker compose exec php php bin/console doctrine:fixtures:load --no-interaction --group=dev || echo "No fixtures"

worker-logs:
	docker compose logs -f php-worker

cache-clear:
	docker compose exec php php bin/console cache:clear

messenger-failed:
	docker compose exec php php bin/console messenger:failed:show

messenger-retry:
	docker compose exec php php bin/console messenger:failed:retry

symfony-new:
	docker run --rm -v $$(pwd)/symfony:/app -w /app composer:2 create-project symfony/skeleton . "7.3.*"

composer-req:
	docker compose exec php composer require $(pkg)

test-php:
	docker compose exec php php bin/phpunit

test-python:
	docker compose exec python-evaluator pytest -v

test:
	$(MAKE) test-php
	$(MAKE) test-python

restart:
	docker compose restart

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d
