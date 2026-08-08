#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

mkdir -p data/uploads data/hf-cache

exec "$@"
