// Endereço da API. Local: a API direto na porta 8000. Publicado: "/api" no próprio site, que a Vercel
// repassa para o Render (vercel.json). Assim o navegador fala com um endereço só e não precisa de CORS.
const LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
export const API_URL = LOCAL ? "http://localhost:8000" : "/api";

// Senha dos usuários de demonstração. É pública de propósito (está no README)
// e precisa ser igual ao DEMO_PASSWORD do .env usado no seed.
export const DEMO_PASSWORD = "helpboard123";

export const DEMO_USERS = [
  { name: "Ana", role: "ADMIN", email: "admin@helpboard.dev" },
  { name: "Maria", role: "TECNICO", email: "maria@helpboard.dev" },
  { name: "Carlos", role: "TECNICO", email: "carlos@helpboard.dev" },
  { name: "João", role: "SOLICITANTE", email: "joao@helpboard.dev" },
];

// Dias que um chamado RESOLVIDO espera o solicitante antes de fechar sozinho (AUTO_CLOSE_DAYS da API)
export const AUTO_CLOSE_DAYS = 7;
