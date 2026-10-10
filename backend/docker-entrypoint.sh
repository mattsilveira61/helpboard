#!/bin/sh
# Inicialização da API no contêiner: aplica as migrations, cria os dados de demonstração e sobe o servidor.
set -e

echo "Aplicando migrations..."
alembic upgrade head

# O seed é idempotente: rodar de novo não duplica nada
if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "Criando dados de demonstração..."
  python -m app.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
