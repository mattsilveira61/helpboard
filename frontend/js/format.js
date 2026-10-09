// Datas da API (ISO em UTC) exibidas no fuso e no formato do navegador.

const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const date = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });
const relative = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

export function formatDateTime(iso) {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

export function formatDate(iso) {
  return iso ? date.format(new Date(iso)) : "—";
}

const UNITS = [
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];

/** "há 3 horas", "em 2 dias", "agora". */
export function formatRelative(iso, now = Date.now()) {
  const seconds = (new Date(iso).getTime() - now) / 1000;
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "agora";
}
