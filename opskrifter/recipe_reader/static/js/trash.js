// Papirkurven: slettede opskrifter kan hentes tilbage eller slettes endeligt.
import { action, el, send, toast } from "./dom.js";
import { formatDate } from "./format.js";
import { go, href } from "./routes.js";
import { back } from "./recipe.js";

const view = () => document.getElementById("papirkurv");
const trashUrl = (id) => `api/papirkurv/${encodeURIComponent(id)}`;

async function restore(item) {
  const result = await send(`${trashUrl(item.id)}/hent-tilbage`, { method: "POST" }, "Opskriften kunne ikke hentes tilbage. Prøv igen.");
  if (!result) return;
  toast(`„${item.titel}“ er tilbage i biblioteket.`);
  go(href.recipe(result.id));
}

async function deletePermanently(item) {
  const result = await send(trashUrl(item.id), { method: "DELETE" }, "Opskriften kunne ikke slettes. Prøv igen.");
  if (!result) return;
  toast(`„${item.titel}“ er slettet endeligt.`);
  show();
}

function row(item) {
  const actions = el("div", { class: "trash-actions" });
  const normal = () =>
    actions.replaceChildren(action("Hent tilbage", () => restore(item)), " · ", action("Slet endeligt", confirm));
  // Endelig sletning kan ikke fortrydes, så den skal bekræftes.
  const confirm = () =>
    actions.replaceChildren(
      el("span", { class: "confirm" }, "Slet endeligt? Det kan ikke fortrydes. "),
      action("Ja, slet", () => deletePermanently(item), { class: "danger" }),
      " · ",
      action("Annullér", normal),
    );
  normal();
  return el(
    "div",
    { class: "trash-row" },
    el("div", { class: "row-t" }, item.titel),
    el("div", { class: "row-s" }, `Slettet ${formatDate(item.slettet)}`),
    actions,
  );
}

export async function show() {
  view().replaceChildren(back(), el("h1", { class: "title" }, "Papirkurv"));
  const items = await send("api/papirkurv", {}, "Papirkurven kunne ikke hentes. Prøv igen om lidt.");
  if (!items) return;
  view().append(...(items.length ? items.map(row) : [el("p", { class: "empty" }, "Papirkurven er tom.")]));
}
