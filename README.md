# HelpBoard

Sistema de gestão de chamados e suporte com quadro Kanban — FastAPI, PostgreSQL e JavaScript puro.

> 🚧 Em desenvolvimento. Planejamento completo em [docs/Planejamento.md](docs/Planejamento.md).

## Rodando localmente

Pré-requisitos: Python 3.12+, Docker Desktop.

```bash
# 1. Variáveis de ambiente
cp .env.example .env            # Windows: copy .env.example .env

# 2. Banco PostgreSQL
docker compose up -d

# 3. Ambiente Python
python -m venv backend/.venv
backend/.venv/Scripts/activate  # Linux/Mac: source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt

# 4. API
uvicorn app.main:app --reload --app-dir backend
```

- API: http://localhost:8000
- Documentação Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Testes

```bash
pytest
```
