// A API usa códigos sem acento; os textos exibidos ficam aqui.

export const ROLE_LABELS = {
  ADMIN: "Admin",
  TECNICO: "Técnico",
  SOLICITANTE: "Solicitante",
};

export const STATUS_LABELS = {
  ABERTO: "Aberto",
  EM_ANDAMENTO: "Em andamento",
  RESOLVIDO: "Resolvido",
  FECHADO: "Fechado",
};

// Na ordem de exibição: da mais urgente para a menos urgente
export const PRIORITY_LABELS = {
  CRITICA: "Crítica",
  ALTA: "Alta",
  MEDIA: "Média",
  BAIXA: "Baixa",
};

// Regra 11: prazo em horas corridas a partir da abertura (igual a app/services/sla.py)
export const SLA_HOURS = {
  CRITICA: 4,
  ALTA: 8,
  MEDIA: 24,
  BAIXA: 72,
};
