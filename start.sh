#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Checking app imports..."
python -c "
import traceback
try:
    from app.main import app
    print('Import OK')
except Exception as e:
    traceback.print_exc()
    raise SystemExit(1)
"

echo "Starting server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
