// Página provisória: monta o layout e avisa em qual etapa o conteúdo chega.
// Cada página ganha o seu próprio script quando a etapa dela for feita.

import { emptyState } from "../dom.js";
import { initPage } from "../layout.js";

const { page, stage } = document.body.dataset;
const { main } = await initPage(page);

main.append(emptyState("Em construção", `Esta tela chega na Etapa ${stage} do projeto.`));
