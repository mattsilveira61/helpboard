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
| `GET /categories` | autenticado | Categorias ativas em ordem alfabética (`include_inactive=true` só para admin) |
| `GET /categories/{id}` | autenticado | Detalha a categoria |
| `POST /categories` | admin | Cria categoria (nome único, sem diferenciar maiúsculas) |
| `PATCH /categories/{id}` | admin | Altera os campos enviados (inclusive reativar) |
| `DELETE /categories/{id}` | admin | Desativa a categoria: some do formulário, mas continua nos chamados antigos |

## Chamados

Cada perfil só enxerga parte dos chamados: o admin vê todos, o técnico vê os atribuídos a ele e os disponíveis
(sem responsável), e o solicitante vê só os que abriu. Chamado fora do alcance responde `404`.

| Endpoint | Quem acessa | Descrição |
|---|---|---|
| `GET /tickets` | autenticado | Lista paginada dos chamados visíveis, críticos primeiro, com filtros (abaixo) |
| `POST /tickets` | autenticado | Abre chamado em nome do usuário logado (status `ABERTO`, prazo pela prioridade) |
| `GET /tickets/{id}` | autenticado | Detalha o chamado, com `is_overdue` indicando atraso no prazo |
| `PATCH /tickets/{id}` | conforme o campo | Edita título, descrição, categoria e prioridade (matriz de permissões) |
| `PUT /tickets/{id}/assignee` | admin | Atribui, reatribui ou remove (`null`) o responsável |
| `POST /tickets/{id}/assume` | técnico | Assume um chamado `ABERTO` sem responsável |
| `POST /tickets/{id}/status` | conforme a transição | Muda o status. `RESOLVIDO` exige `solution`; recusar a solução e reabrir exigem `reason` |
| `DELETE /tickets/{id}` | admin | Arquiva o chamado (não há exclusão física) |
| `GET /tickets/{id}/comments` | quem vê o chamado | Comentários em ordem cronológica |
| `POST /tickets/{id}/comments` | quem vê o chamado | Comenta em nome do usuário logado (não em chamado fechado ou arquivado) |
| `GET /tickets/{id}/history` | quem vê o chamado | Linha do tempo das alterações: quem fez, o quê, valor antigo e novo |

Comentários não podem ser editados nem apagados, para servir de registro de auditoria.

### Filtros e paginação de `GET /tickets`

| Parâmetro | Exemplo | Observação |
|---|---|---|
| `status`, `priority` | `?status=ABERTO&status=EM_ANDAMENTO` | Repita o parâmetro para escolher vários |
| `category_id`, `assigned_to_id`, `requester_id` | `?category_id=3` | |
| `unassigned` | `?unassigned=true` | Só os sem responsável |
| `created_from`, `created_to` | `?created_from=2026-10-01&created_to=2026-10-31` | Dias inclusivos, no fuso `TIMEZONE` (padrão `America/Sao_Paulo`) |
| `q` | `?q=impressora` ou `?q=#42` | Palavra no título ou na descrição; um número busca também pelo ID |
| `include_archived` | `?include_archived=true` | Só tem efeito para o admin |
| `page`, `page_size` | `?page=2&page_size=20` | `page_size` de 1 a 100 (padrão 20) |

Os filtros se combinam e nunca furam a visibilidade do perfil. A resposta tem o formato
`{"items": [...], "total": 57, "page": 2, "page_size": 20, "pages": 3}`.

Fluxo de status: `ABERTO → EM_ANDAMENTO → RESOLVIDO → FECHADO`, com volta à fila (`EM_ANDAMENTO → ABERTO`),
solução recusada (`RESOLVIDO → EM_ANDAMENTO`) e reabertura (`FECHADO → ABERTO`). Detalhes em
[docs/Planejamento.md](docs/Planejamento.md). Toda alteração grava o histórico na mesma transação.

## Dashboard

`GET /dashboard` (admin e técnico) devolve todos os indicadores numa resposta só. Cada número é calculado
pelo PostgreSQL com `GROUP BY`, `COUNT(*) FILTER (...)`, `LEFT JOIN` e `AVG`, sem carregar os chamados na memória.
O admin vê todos os chamados (`"scope": "TODOS"`); o técnico, só os atribuídos a ele (`"scope": "MEUS"`).
Chamados arquivados não entram na conta.

| Bloco | Conteúdo |
|---|---|
| `backlog` | Fila de agora: abertos, em andamento, críticos, atrasados (SLA vencido) e sem responsável |
| `created` | Abertos no período: total e divisão por status, prioridade e categoria |
| `resolved` | Resolvidos no período e tempo médio de resolução em horas (da abertura até a solução) |
| `timeline` | Abertos e resolvidos dia a dia, inclusive os dias sem movimento (pronto para um gráfico) |
| `by_assignee` | Por técnico: abertos, em andamento, resolvidos no período e tempo médio |

O período vem de `start` e `end` (`?start=2026-03-01&end=2026-03-31`). O padrão são os últimos 30 dias, e o
máximo é 366 dias. Os dias seguem o fuso `TIMEZONE`.

Respostas de erro: `401` sem login ou token inválido, `403` perfil sem permissão, `404` não encontrado,
`409` regra de negócio violada (ex.: e-mail repetido, transição de status fora do fluxo), `422` dados inválidos.

## Testes

```bash
pytest
```

Os testes usam o banco `helpboard_test` (variável `TEST_DATABASE_URL`), recriado pelas migrations a cada execução.
Cada teste roda dentro de uma transação desfeita no final, então o banco de desenvolvimento nunca é alterado.
