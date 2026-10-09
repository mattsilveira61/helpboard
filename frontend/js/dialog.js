// Diálogo modal (elemento <dialog> nativo) para confirmar ações e pedir textos como solução ou motivo.

import { el, setAlert } from "./dom.js";

let counter = 0;

function fieldControl(field, prefix) {
  const id = `${prefix}-${field.name}`;
  const control =
    field.type === "select"
      ? el(
          "select",
          { class: "input", id, name: field.name },
          field.options.map((option) =>
            el("option", { value: option.value, selected: option.value === field.value }, option.label),
          ),
        )
      : el("textarea", { class: "input", id, name: field.name, rows: 5, maxlength: field.maxlength }, field.value ?? "");
  return el("div", { class: "field" }, el("label", { for: id }, field.label), control);
}

/**
 * Abre o diálogo e espera a pessoa confirmar ou cancelar.
 * Ao confirmar, roda `onConfirm(valores)` com o diálogo aberto: se a API recusar, a mensagem aparece
 * dentro do diálogo e o texto digitado não se perde. Devolve o resultado de `onConfirm`, ou null se cancelar.
 *
 * fields: [{ name, label, type: "textarea" | "select", options: [{ value, label }], value, required }]
 */
export function openDialog({ title, text, fields = [], confirmLabel = "Confirmar", danger = false, onConfirm }) {
  return new Promise((resolve) => {
    const prefix = `dialog-${++counter}`;
    let result = null;
    let busy = false;

    const alertBox = el("p", { class: "alert", role: "alert", hidden: true });
    const confirm = el(
      "button",
      { type: "submit", class: `button ${danger ? "button-danger" : "button-primary"}` },
      confirmLabel,
    );
    const cancel = el(
      "button",
      { type: "button", class: "button button-secondary", onClick: () => dialog.close() },
      "Cancelar",
    );
    const form = el(
      "form",
      { class: "dialog-form", novalidate: true },
      el("h2", { id: `${prefix}-title`, class: "dialog-title" }, title),
      text && el("p", { class: "dialog-text" }, text),
      fields.map((field) => fieldControl(field, prefix)),
      alertBox,
      el("div", { class: "dialog-actions" }, cancel, confirm),
    );
    const dialog = el("dialog", { class: "dialog", "aria-labelledby": `${prefix}-title` }, form);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form));
      // A API também recusa texto só com espaços, mas aqui a mensagem sai em português e sem ida ao servidor
      const missing = fields.find((field) => field.required && !values[field.name].trim());
      if (missing) {
        setAlert(alertBox, `Preencha o campo "${missing.label}".`);
        form.elements[missing.name].focus();
        return;
      }

      busy = confirm.disabled = cancel.disabled = true;
      try {
        result = onConfirm ? await onConfirm(values) : values;
        busy = false;
        dialog.close();
      } catch (error) {
        busy = confirm.disabled = cancel.disabled = false;
        setAlert(alertBox, error.message);
      }
    });

    // Esc fecha o diálogo, menos enquanto a ação está sendo enviada
    dialog.addEventListener("cancel", (event) => {
      if (busy) event.preventDefault();
    });
    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(result);
    });

    document.body.append(dialog);
    dialog.showModal();
  });
}
