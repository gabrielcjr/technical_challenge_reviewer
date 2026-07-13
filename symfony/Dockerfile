FROM php:8.4-fpm

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    unzip \
    libpq-dev \
    libicu-dev \
    libzip-dev \
    libonig-dev \
    libxml2-dev \
    zlib1g-dev \
    curl \
    && docker-php-ext-install \
        pdo \
        pdo_pgsql \
        intl \
        zip \
        opcache \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Composer
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

# Symfony CLI not strictly needed, but useful
RUN curl -1sLf 'https://dl.cloudsmith.io/public/symfony/stable/setup.deb.sh' | bash || true
RUN apt-get update && apt-get install -y symfony-cli || echo "symfony-cli optional"

WORKDIR /var/www/symfony

# Copy composer files first for cache
COPY composer.json composer.lock* ./

# Set composer to not need root warning
ENV COMPOSER_ALLOW_SUPERUSER=1

# Install deps if composer.json exists, else skip (for initial scaffolding)
RUN if [ -f composer.json ]; then composer install --no-scripts --no-autoloader --prefer-dist --no-progress || true; fi

# Copy rest of app
COPY . .

# Run composer dump if needed
RUN if [ -f composer.json ]; then composer dump-autoload --optimize || true; fi

# Fix permissions
RUN mkdir -p var/cache var/log && chmod -R 777 var || true

EXPOSE 9000

CMD ["php-fpm"]
