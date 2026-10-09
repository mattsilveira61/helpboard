// Helpers para montar a tela. Todo texto entra como texto (nunca como HTML), o que impede XSS
// mesmo quando o conteúdo veio de um usuário, como o título de um chamado.

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Cria um elemento: el("a", { href: "x.html", class: "link" }, "Texto", outroElemento).
 * Propriedades que começam com "on" viram eventos (onClick → click).
 */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...children.flat().filter((child) => child !== undefined && child !== null && child !== false));
  return node;
}

// Ícones de traço no estilo Feather (MIT): cada um é uma lista de caminhos SVG
const ICONS = {
  dashboard: ["M3 3h7v9H3z", "M14 3h7v5h-7z", "M14 12h7v9h-7z", "M3 16h7v5H3z"],
  board: ["M4 4h4v16H4z", "M10 4h4v10h-4z", "M16 4h4v13h-4z"],
  list: ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"],
  users: [
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2",
    "M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0",
    "M22 21v-2a4 4 0 0 0-3-3.87",
    "M16 3.13a4 4 0 0 1 0 7.75",
  ],
  tag: ["M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z", "M7 7h.01"],
  logout: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"],
  menu: ["M3 6h18", "M3 12h18", "M3 18h18"],
  tool: [
    "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z",
  ],
};

export function icon(name) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  for (const d of ICONS[name]) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

/** Bloco de aviso para telas vazias ou ainda em construção. */
export function emptyState(title, text, iconName = "tool") {
  return el(
    "section",
    { class: "empty-state" },
    el("div", { class: "empty-state-icon" }, icon(iconName)),
    el("h2", {}, title),
    el("p", {}, text),
  );
}

/** Mostra (ou esconde, com texto vazio) uma mensagem num elemento de alerta. */
export function setAlert(node, text, kind = "error") {
  node.textContent = text ?? "";
  node.className = `alert alert-${kind}`;
  node.hidden = !text;
}
