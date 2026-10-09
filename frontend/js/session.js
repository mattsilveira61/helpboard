// Sessão do usuário. O token fica no sessionStorage: some ao fechar a aba e não é enviado
// automaticamente pelo navegador (sem risco de CSRF).

const TOKEN_KEY = "helpboard.token";
const USER_KEY = "helpboard.user";

export function saveSession(token, user) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function updateUser(user) {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

export function isLoggedIn() {
  return Boolean(getToken() && getUser());
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

/** Página inicial de cada perfil. */
export function homeFor(user) {
  return user.role === "SOLICITANTE" ? "board.html" : "dashboard.html";
}

/** Só aceita voltar para uma página do próprio sistema (evita redirecionar para sites externos). */
export function safeNext(value) {
  if (!value || !/^[a-z][a-z-]*\.html(\?[^#]*)?$/.test(value) || value.startsWith("login.html")) {
    return null;
  }
  return value;
}

/** Vai para o login e guarda a página atual para voltar depois de entrar. */
export function goToLogin(reason) {
  const params = new URLSearchParams();
  const current = location.pathname.split("/").pop() + location.search;
  if (safeNext(current)) params.set("next", current);
  if (reason) params.set("reason", reason);
  const query = params.toString();
  location.replace(query ? `login.html?${query}` : "login.html");
}

export function logout() {
  clearSession();
  location.replace("login.html?reason=logout");
}

/** Promise que nunca termina: um `await halt()` interrompe o script enquanto o navegador troca de página. */
export function halt() {
  return new Promise(() => {});
}
