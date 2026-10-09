// Única porta de entrada para a API: monta a URL, envia o token e transforma erros em mensagens.

import { API_URL } from "./config.js";
import { clearSession, getToken, goToLogin, halt } from "./session.js";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function errorMessage(status, body) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  // 422: o FastAPI devolve uma lista com um item por campo inválido
  // (as validações próprias chegam como "Value error, <mensagem>")
  if (Array.isArray(detail)) return detail.map((item) => item.msg.replace(/^Value error, /, "")).join(" ");
  return `Erro inesperado na API (${status}).`;
}

function buildUrl(path, query = {}) {
  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(query)) {
    // Listas viram o parâmetro repetido (?status=ABERTO&status=EM_ANDAMENTO); vazios são ignorados
    for (const item of [value].flat()) {
      if (item !== undefined && item !== null && item !== "") url.searchParams.append(key, item);
    }
  }
  return url;
}

export async function request(path, { method = "GET", body, query, auth = true } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Não foi possível conectar à API. Verifique se ela está no ar.");
  }

  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.ok) return data;

  if (response.status === 401 && token) {
    // Token vencido ou usuário desativado: a sessão acabou
    clearSession();
    goToLogin("expired");
    return halt();
  }
  throw new ApiError(response.status, errorMessage(response.status, data));
}

export const api = {
  get: (path, query) => request(path, { query }),
  post: (path, body, options = {}) => request(path, { method: "POST", body, ...options }),
  put: (path, body) => request(path, { method: "PUT", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};
