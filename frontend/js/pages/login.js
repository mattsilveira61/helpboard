import { api } from "../api.js";
import { DEMO_PASSWORD, DEMO_USERS } from "../config.js";
import { el, setAlert } from "../dom.js";
import { ROLE_LABELS } from "../labels.js";
import { homeFor, isLoggedIn, getUser, safeNext, saveSession } from "../session.js";

const REASONS = {
  expired: ["Sua sessão expirou. Entre novamente.", "info"],
  logout: ["Você saiu do sistema.", "info"],
};

const params = new URLSearchParams(location.search);
const form = document.querySelector("#login-form");
const alertBox = document.querySelector("#login-alert");
const submit = form.querySelector("button[type=submit]");
const demoButtons = document.querySelector("#demo-buttons");

function goHome(user) {
  location.replace(safeNext(params.get("next")) ?? homeFor(user));
}

function setBusy(busy) {
  for (const button of document.querySelectorAll("button")) button.disabled = busy;
  submit.textContent = busy ? "Entrando…" : "Entrar";
}

async function login(email, password) {
  setAlert(alertBox, "");
  setBusy(true);
  try {
    const { access_token: token, user } = await api.post("/auth/login", { email, password }, { auth: false });
    saveSession(token, user);
    goHome(user);
  } catch (error) {
    setAlert(alertBox, error.message);
    setBusy(false);
  }
}

if (isLoggedIn()) {
  goHome(getUser());
} else {
  const reason = REASONS[params.get("reason")];
  if (reason) setAlert(alertBox, ...reason);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    login(form.email.value.trim(), form.password.value);
  });

  for (const demo of DEMO_USERS) {
    demoButtons.append(
      el(
        "button",
        { type: "button", class: "demo-button", onClick: () => login(demo.email, DEMO_PASSWORD) },
        el("strong", {}, demo.name),
        el("span", { class: `role-badge role-${demo.role.toLowerCase()}` }, ROLE_LABELS[demo.role]),
      ),
    );
  }
}
