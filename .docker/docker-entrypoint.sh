#!/bin/sh
set -e

echo "Installing Composer dependencies..."
composer install --no-interaction --optimize-autoloader

echo "Running migrations..."
php bin/console doctrine:migrations:migrate --no-interaction --allow-no-migration

echo "Setting up messenger transports..."
php bin/console messenger:setup-transports --no-interaction

echo "Initializing test database environment..."
php bin/console doctrine:database:create --env=test --if-not-exists --no-interaction
php bin/console doctrine:migrations:migrate --env=test --no-interaction --allow-no-migration
php bin/console messenger:setup-transports --env=test --no-interaction

echo "Application setup complete. Starting php-fpm..."
exec php-fpm
