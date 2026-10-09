// Endereço da API. No deploy (Etapa 14) passa a apontar para o servidor publicado.
export const API_URL = "http://localhost:8000";

// Senha dos usuários de demonstração. É pública de propósito (está no README)
// e precisa ser igual ao DEMO_PASSWORD do .env usado no seed.
export const DEMO_PASSWORD = "helpboard123";

export const DEMO_USERS = [
  { name: "Ana", role: "ADMIN", email: "admin@helpboard.dev" },
  { name: "Maria", role: "TECNICO", email: "maria@helpboard.dev" },
  { name: "Carlos", role: "TECNICO", email: "carlos@helpboard.dev" },
  { name: "João", role: "SOLICITANTE", email: "joao@helpboard.dev" },
];
