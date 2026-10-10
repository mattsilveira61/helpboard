# HelpBoard

Sistema de gestão de chamados e suporte com quadro Kanban — FastAPI, PostgreSQL e JavaScript puro.

![Quadro Kanban](docs/screenshots/quadro.png)

## O problema

Numa empresa pequena, os pedidos de suporte chegam soltos: WhatsApp, e-mail, telefone, corredor. Ninguém sabe
quem está cuidando de quê, o que está atrasado nem quanto tempo cada problema leva para ser resolvido.

O HelpBoard junta tudo num lugar só. Cada pedido vira um chamado com responsável, prioridade, prazo (SLA),
conversa e histórico, e a equipe acompanha a fila num quadro Kanban e num dashboard com os números do período.

## Funcionalidades

- **Três perfis**:
  - o **solicitante** abre e acompanha os próprios chamados;
  - o **técnico** assume e resolve;
  - o **admin** vê tudo, atribui, gerencia usuários e categorias.
- **Fluxo de status validado no servidor**: `ABERTO → EM_ANDAMENTO → RESOLVIDO → FECHADO`, com devolução à fila,
  recusa da solução e reabertura. Resolver exige a solução; recusar e reabrir exigem o motivo.
- **Prazo automático por prioridade** (Crítica 4 h, Alta 8 h, Média 24 h, Baixa 72 h), com aviso de atraso.
- **Quadro Kanban** com arrastar e soltar (e um menu para quem não usa mouse).
- **Lista** com busca, filtros combinados e paginação.
- **Comentários e histórico automático**: quem fez o quê e quando, gravado na mesma transação da mudança.
- **Dashboard** com indicadores calculados no PostgreSQL: fila atual, abertos × resolvidos por dia, tempo médio
  de resolução, divisão por prioridade, categoria e técnico.
- **Nada é apagado**: chamados são arquivados, e usuários e categorias, desativados. Comentários não se editam.
- Tema claro e escuro automático, layout para celular e botões de login rápido com usuários de demonstração.

## Telas

| Dashboard | Detalhe do chamado |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Detalhe](docs/screenshots/detalhe.png) |
| **Lista com filtros** | **Tema escuro** |
| ![Lista](docs/screenshots/lista.png) | ![Quadro no tema escuro](docs/screenshots/quadro-escuro.png) |

<p align="center">
  <img src="docs/screenshots/celular.png" alt="Lista no celular" width="260">
  &nbsp;&nbsp;
  <img src="docs/screenshots/login.png" alt="Tela de login" width="520">
</p>

## Stack

| Camada | Tecnologia |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2 |
| Banco | PostgreSQL 16, SQLAlchemy 2 (ORM), Alembic (migrations) |
| Autenticação | JWT (PyJWT) + senhas com bcrypt |
| Frontend | HTML, CSS e JavaScript puro (módulos ES), sem framework e sem build |
| Testes | pytest (192 testes, com banco PostgreSQL real) |
| Infra | Docker Compose (postgres + api + nginx) |

## Arquitetura

```mermaid
flowchart LR
    B["Navegador<br/>HTML + CSS + JS"] -- "fetch + JWT<br/>JSON" --> A["API FastAPI"]
    A -- SQLAlchemy --> D[("PostgreSQL")]
```

O backend é dividido em camadas, e as regras de negócio ficam todas em `services/`:

```text
backend/app/
├── routers/   recebem a requisição, validam com os schemas e checam o perfil
├── schemas/   Pydantic: formato de entrada e saída (e a documentação do Swagger)
├── services/  regras de negócio: transições, permissões, histórico, SLA, dashboard
├── models/    tabelas SQLAlchemy
└── core/      configuração, segurança (JWT, hash), conexão com o banco e erros
```

### Modelo de dados

```mermaid
erDiagram
    users ||--o{ tickets : "abre (requester_id)"
    users ||--o{ tickets : "atende (assigned_to_id)"
    categories ||--o{ tickets : classifica
    tickets ||--o{ comments : possui
    users ||--o{ comments : escreve
    tickets ||--o{ ticket_history : registra
    users ||--o{ ticket_history : executa

    users {
        int id PK
        varchar email UK
        varchar role "ADMIN | TECNICO | SOLICITANTE"
        bool is_active
    }
    categories {
        int id PK
        varchar name UK
        bool is_active
    }
    tickets {
        int id PK
        varchar title
        varchar status
        varchar priority
        int category_id FK
        int requester_id FK
        int assigned_to_id FK "nullable"
        timestamptz sla_deadline
        text solution "obrigatória se RESOLVIDO/FECHADO"
        bool is_archived
    }
    comments {
        int id PK
        int ticket_id FK
        int user_id FK
        text message
    }
    ticket_history {
        int id PK
        int ticket_id FK
        int user_id FK
        varchar action
        text old_value
        text new_value
    }
```

O banco também protege as regras: `CHECK` nos valores de perfil, status e prioridade, solução obrigatória em
chamado resolvido ou fechado, e-mail e nome de categoria únicos, chaves estrangeiras sem exclusão em cascata e
índices nas colunas usadas pelos filtros. O modelo completo, a matriz de permissões e as 14 regras de negócio
estão em [docs/Planejamento.md](docs/Planejamento.md).

## Rodando com Docker (um comando)

Pré-requisito: Docker Desktop.

```bash
cp .env.example .env            # Windows: copy .env.example .env
docker compose up --build
```

- Aplicação: http://localhost:5500
- API e Swagger: http://localhost:8000/docs

Sobem três contêineres: `postgres` (banco), `api` (FastAPI) e `web` (nginx servindo o frontend).
A cada inicialização a API aplica as migrations e roda o seed, que é idempotente: os usuários de
demonstração são criados uma vez e reiniciar não duplica nada. Para subir sem os dados de exemplo, defina
`SEED_DEMO=false` no `.env`. Os dados ficam no volume `pgdata`; `docker compose down -v` apaga tudo.

## Rodando para desenvolver

Pré-requisitos: Python 3.12+, Docker Desktop.

```bash
# 1. Variáveis de ambiente
cp .env.example .env            # Windows: copy .env.example .env

# 2. Só o banco PostgreSQL (a API roda fora do Docker, com recarga automática)
docker compose up -d postgres

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

# 6. Frontend (em outro terminal)
python -m http.server 5500 --directory frontend
```

- Aplicação: http://localhost:5500
- API: http://localhost:8000
- Documentação Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

O frontend é HTML, CSS e JavaScript puro (módulos ES), sem etapa de build. A porta 5500 precisa estar em
`CORS_ORIGINS`, e o endereço da API fica em `frontend/js/config.js`.

### Variáveis de ambiente

Todas ficam no `.env`, que nunca vai para o Git. O `.env.example` traz valores prontos para rodar localmente.

| Variável | Para que serve |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | Credenciais do contêiner PostgreSQL |
| `DATABASE_URL` | Conexão da API com o banco (`postgresql+psycopg://usuario:senha@host:porta/banco`) |
| `TEST_DATABASE_URL` | Banco usado pelo pytest (é apagado e recriado a cada execução) |
| `SECRET_KEY` | Chave que assina os tokens JWT. Em produção, gere uma forte (comando no `.env.example`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do login (padrão 60) |
| `CORS_ORIGINS` | Endereços do frontend autorizados a chamar a API, separados por vírgula |
| `TIMEZONE` | Fuso dos filtros por data e do dashboard (o banco guarda tudo em UTC) |
| `DEMO_PASSWORD` | Senha dos usuários de demonstração criados pelo seed |
| `SEED_DEMO` | `false` faz o contêiner da API subir sem os dados de exemplo |

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

## Frontend

```
frontend/
├── *.html          uma página por tela (login, dashboard, quadro, chamados, usuários, categorias)
├── css/style.css   tokens de cor, tema claro/escuro e layout responsivo
└── js/
    ├── config.js   endereço da API e usuários de demonstração
    ├── api.js      fetch com token, mensagens de erro da API e sessão expirada
    ├── labels.js   nomes em português de status, prioridades e perfis
    ├── session.js  token e usuário no sessionStorage, página inicial por perfil
    ├── layout.js   menu lateral, guarda de páginas por perfil e topo
    ├── dom.js      criação de elementos, ícones, estados vazios e avisos (toasts)
    ├── dialog.js   diálogo modal para confirmar ações e pedir solução ou motivo
    ├── format.js   datas no formato brasileiro e tempo relativo ("há 2 horas")
    ├── tickets.js  selos de status, prioridade e prazo, e o que cada perfil pode fazer
    ├── filters.js  filtros compartilhados entre a lista e o quadro
    ├── admin.js    tabela, busca e confirmações das telas de usuários e categorias
    └── pages/      o script de cada página
```

### Telas de chamados

- **Lista** (`tickets.html`): busca por título, descrição ou número; filtros de status, prioridade, categoria, responsável e período; paginação. Os filtros ficam no endereço da página, então recarregar, voltar do detalhe ou compartilhar o link mostra a mesma lista. No celular, cada linha vira um cartão.
- **Formulário** (`ticket-form.html`): abre um chamado novo ou edita um existente (`?id=N`). Os erros aparecem em cada campo antes de enviar, com as mesmas regras da API. Na edição, só os campos que o perfil pode alterar ficam habilitados e só o que mudou é enviado.
- **Detalhe** (`ticket.html?id=N`): dados do chamado, prazo do SLA, comentários e histórico. Os botões mudam conforme o perfil e o status: assumir, iniciar atendimento, resolver (pede a solução), aceitar e fechar, recusar ou reabrir (pedem o motivo, que vira comentário), trocar responsável e arquivar.

- Na tela de login há botões para entrar direto com cada usuário de demonstração.
- O menu mostra só as telas do perfil: o solicitante vê Quadro e Chamados; o técnico, também o Dashboard; o admin, também Usuários e Categorias. Abrir uma página proibida pelo endereço leva de volta à página inicial. A proteção real fica na API, que responde `403`.
- Se o token vencer, qualquer resposta `401` encerra a sessão e volta ao login com aviso.
- Todo texto vindo da API entra na página como texto (`textContent`), nunca como HTML, o que evita XSS.

## Testes

```bash
pytest
```

Os testes usam o banco `helpboard_test` (variável `TEST_DATABASE_URL`), recriado pelas migrations a cada execução.
Cada teste roda dentro de uma transação desfeita no final, então o banco de desenvolvimento nunca é alterado.

São 192 testes que cobrem as 14 regras de negócio do planejamento:
- permissões de cada perfil e transições de status;
- prazo e atraso;
- histórico gravado na mesma transação (se o histórico falha, a mudança é desfeita);
- filtros e indicadores do dashboard;
- erro 500 sem vazar detalhes internos.

## Decisões técnicas

- **Regras no backend, em `services/`.** O frontend só esconde os botões que o perfil não pode usar. Quem decide
  é a API, que responde `403` ou `409`. Assim as regras valem também para quem chama a API direto, e cada uma
  pode ser testada sem passar pelo HTTP.
- **O banco também valida.** Além do Pydantic, os `CHECK` e `UNIQUE` do PostgreSQL garantem os dados mesmo se
  alguém escrever direto no banco. Os enums são `VARCHAR` + `CHECK`, e não o tipo `ENUM` do Postgres, que é mais
  difícil de alterar numa migration.
- **Chamado fora do alcance responde `404`, não `403`.** Assim ninguém descobre por tentativa quais números de
  chamado existem.
- **Nada é apagado.** Arquivar e desativar preservam o histórico e as estatísticas, que é o que um sistema de
  suporte precisa para auditoria.
- **Dashboard calculado pelo PostgreSQL** (`COUNT(*) FILTER`, `GROUP BY`, `AVG`), sem carregar os chamados na
  memória da API. O agrupamento por dia usa o fuso da empresa, e não o UTC.
- **Frontend sem framework e sem build.** Módulos ES nativos, `<dialog>` nativo e drag-and-drop HTML5. Todo
  texto vindo da API entra por `textContent`, o que fecha a porta para XSS.
- **Testes contra PostgreSQL real**, e não SQLite. As constraints, o fuso e as consultas do dashboard só se
  comportam igual à produção no mesmo banco.

## Aprendizados

- Desenhar o fluxo de status e a matriz de permissões antes do código (o [planejamento](docs/Planejamento.md))
  fez as regras virarem uma tabela de transições simples e testável, em vez de `if`s espalhados.
- Agrupar por dia num fuso diferente de UTC no PostgreSQL exige cuidado: com o fuso enviado como parâmetro
  comum, o banco não reconhece o `SELECT` e o `GROUP BY` como a mesma expressão.
- Rodar cada teste dentro de uma transação desfeita no final deixa a suíte rápida e independente, sem
  precisar limpar o banco entre um teste e outro.
- Registrar o tratamento do erro 500 por dentro do CORS faz o navegador receber a mensagem de erro. Sem isso,
  ele mostra um erro de CORS que esconde a causa real.
