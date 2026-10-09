// Página de entrada: manda cada um para o lugar certo.
import { getUser, homeFor, isLoggedIn } from "../session.js";

location.replace(isLoggedIn() ? homeFor(getUser()) : "login.html");
