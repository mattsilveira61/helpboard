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

# 4. Tabelas e dados de demonstração
cd backend
alembic upgrade head
python -m app.seed
cd ..

# 5. API
uvicorn app.main:app --reload --app-dir backend
```

- API: http://localhost:8000
- Documentação Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Usuários de demonstração

Criados pelo seed, todos com a senha definida em `DEMO_PASSWORD` (padrão do `.env.example`: `helpboard123`).

| Perfil | E-mail |
|---|---|
| Admin | admin@helpboard.dev |
| Técnico | maria@helpboard.dev |
| Técnico | carlos@helpboard.dev |
| Solicitante | joao@helpboard.dev |

O seed também cria 7 categorias e 20 chamados de exemplo em todos os status, com comentários e histórico.
Ele pode ser executado mais de uma vez sem duplicar dados.

## Testes

```bash
pytest
```

Os testes usam o banco `helpboard_test` (variável `TEST_DATABASE_URL`), recriado pelas migrations a cada execução.
Cada teste roda dentro de uma transação desfeita no final, então o banco de desenvolvimento nunca é alterado.
