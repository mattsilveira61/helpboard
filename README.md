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

## Autenticação

1. `POST /auth/login` com `{"email": "...", "password": "..."}` devolve um `access_token` (JWT).
2. Envie o token nas demais rotas no header `Authorization: Bearer <token>`.
   No Swagger, use o botão **Authorize** e cole o token.

| Endpoint | Quem acessa | Descrição |
|---|---|---|
| `POST /auth/login` | todos | Login, retorna o token e os dados do usuário |
| `GET /auth/me` | autenticado | Dados do usuário logado |
| `GET /users` | admin | Lista usuários (filtros `role` e `active`) |
| `POST /users` | admin | Cria usuário |
| `GET /users/{id}` | admin | Detalha usuário |
| `PATCH /users/{id}` | admin | Altera os campos enviados (inclusive reativar) |
| `DELETE /users/{id}` | admin | Desativa o usuário (não há exclusão física) |

## Chamados

Cada perfil só enxerga parte dos chamados: o admin vê todos, o técnico vê os atribuídos a ele e os disponíveis
(sem responsável), e o solicitante vê só os que abriu. Chamado fora do alcance responde `404`.

| Endpoint | Quem acessa | Descrição |
|---|---|---|
| `GET /tickets` | autenticado | Lista os chamados visíveis, críticos primeiro (`include_archived=true` só para admin) |
| `POST /tickets` | autenticado | Abre chamado em nome do usuário logado (status `ABERTO`, prazo pela prioridade) |
| `GET /tickets/{id}` | autenticado | Detalha o chamado, com `is_overdue` indicando atraso no prazo |
| `PATCH /tickets/{id}` | conforme o campo | Edita título, descrição, categoria e prioridade (matriz de permissões) |
| `PUT /tickets/{id}/assignee` | admin | Atribui, reatribui ou remove (`null`) o responsável |
| `POST /tickets/{id}/assume` | técnico | Assume um chamado `ABERTO` sem responsável |
| `POST /tickets/{id}/status` | conforme a transição | Muda o status. `RESOLVIDO` exige `solution`; recusar a solução e reabrir exigem `reason` |
| `DELETE /tickets/{id}` | admin | Arquiva o chamado (não há exclusão física) |

Fluxo de status: `ABERTO → EM_ANDAMENTO → RESOLVIDO → FECHADO`, com volta à fila (`EM_ANDAMENTO → ABERTO`),
solução recusada (`RESOLVIDO → EM_ANDAMENTO`) e reabertura (`FECHADO → ABERTO`). Detalhes em
[docs/Planejamento.md](docs/Planejamento.md). Toda alteração grava o histórico na mesma transação.

Respostas de erro: `401` sem login ou token inválido, `403` perfil sem permissão, `404` não encontrado,
`409` regra de negócio violada (ex.: e-mail repetido, transição de status fora do fluxo), `422` dados inválidos.

## Testes

```bash
pytest
```

Os testes usam o banco `helpboard_test` (variável `TEST_DATABASE_URL`), recriado pelas migrations a cada execução.
Cada teste roda dentro de uma transação desfeita no final, então o banco de desenvolvimento nunca é alterado.
