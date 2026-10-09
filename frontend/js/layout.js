// Layout das páginas internas: guarda de acesso por perfil, menu lateral e barra superior.

import { api } from "./api.js";
import { el, icon } from "./dom.js";
import { ROLE_LABELS } from "./labels.js";
import { getUser, goToLogin, halt, homeFor, isLoggedIn, logout, updateUser } from "./session.js";

// Mesma matriz da seção 2 do Planejamento. O backend é quem garante as permissões;
// aqui só escondemos o que o perfil não pode usar.
export const PAGES = [
  { id: "dashboard", href: "dashboard.html", label: "Dashboard", icon: "dashboard", roles: ["ADMIN", "TECNICO"] },
  { id: "board", href: "board.html", label: "Quadro", icon: "board", roles: ["ADMIN", "TECNICO", "SOLICITANTE"] },
  { id: "tickets", href: "tickets.html", label: "Chamados", icon: "list", roles: ["ADMIN", "TECNICO", "SOLICITANTE"] },
  { id: "users", href: "users.html", label: "Usuários", icon: "users", roles: ["ADMIN"], admin: true },
  { id: "categories", href: "categories.html", label: "Categorias", icon: "tag", roles: ["ADMIN"], admin: true },
];

function canAccess(page, user) {
  return page.roles.includes(user.role);
}

function navLink(page, current) {
  return el(
    "a",
    { href: page.href, class: "nav-link", "aria-current": page.id === current ? "page" : null },
    icon(page.icon),
    el("span", {}, page.label),
  );
}

function initials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function sidebar(user, current) {
  const allowed = PAGES.filter((page) => canAccess(page, user));
  const main = allowed.filter((page) => !page.admin);
  const admin = allowed.filter((page) => page.admin);

  return el(
    "aside",
    { class: "sidebar", id: "sidebar" },
    el("a", { href: homeFor(user), class: "brand" }, el("span", { class: "brand-mark" }, "HB"), "HelpBoard"),
    el(
      "nav",
      { class: "nav", "aria-label": "Menu principal" },
      main.map((page) => navLink(page, current)),
      admin.length > 0 && el("p", { class: "nav-section" }, "Administração"),
      admin.map((page) => navLink(page, current)),
    ),
    el(
      "div",
      { class: "user-card" },
      el("span", { class: "avatar", "aria-hidden": "true" }, initials(user.name)),
      el(
        "div",
        { class: "user-info" },
        el("strong", { class: "user-name" }, user.name),
        el("span", { class: `role-badge role-${user.role.toLowerCase()}` }, ROLE_LABELS[user.role]),
      ),
      el(
        "button",
        { type: "button", class: "icon-button", title: "Sair", "aria-label": "Sair", onClick: logout },
        icon("logout"),
      ),
    ),
  );
}

function topbar(title, toggleMenu) {
  return el(
    "header",
    { class: "topbar" },
    el(
      "button",
      {
        type: "button",
        class: "icon-button menu-toggle",
        "aria-label": "Abrir menu",
        "aria-controls": "sidebar",
        "aria-expanded": "false",
        onClick: toggleMenu,
      },
      icon("menu"),
    ),
    el("h1", { class: "page-title" }, title),
  );
}

/**
 * Monta a página interna e devolve o usuário e o <main> onde a página desenha seu conteúdo.
 * Quem não está logado vai para o login; quem não tem acesso volta para a sua página inicial.
 */
export async function initPage(pageId) {
  if (!isLoggedIn()) {
    goToLogin();
    return halt();
  }
  const page = PAGES.find((p) => p.id === pageId);
  const user = getUser();
  if (!canAccess(page, user)) {
    location.replace(homeFor(user));
    return halt();
  }

  document.title = `${page.label} · HelpBoard`;
  const main = el("main", { class: "content", id: "content" });
  const shell = el("div", { class: "shell" });

  const toggleMenu = (event) => {
    const open = shell.classList.toggle("menu-open");
    event.currentTarget.setAttribute("aria-expanded", String(open));
  };
  const closeMenu = () => shell.classList.remove("menu-open");

  shell.append(
    sidebar(user, pageId),
    el("div", { class: "backdrop", onClick: closeMenu }),
    el("div", { class: "main-area" }, topbar(page.label, toggleMenu), main),
  );
  document.body.replaceChildren(shell);

  // Confere o token em segundo plano: se venceu ou o usuário foi desativado, a API manda para o login.
  // Se o perfil mudou desde o login, a página é recarregada para refazer a guarda e o menu.
  api.get("/auth/me").then((fresh) => {
    updateUser(fresh);
    if (fresh.role !== user.role || fresh.name !== user.name) location.reload();
  }).catch(() => {});

  return { user, main };
}
