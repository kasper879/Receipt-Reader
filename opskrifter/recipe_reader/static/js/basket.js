// Indkøbskurven: ingredienser fra flere opskrifter, lagt sammen, og sendt til indkøbslisten i Home Assistant på én gang.
import { action, el, json, send, toast } from "./dom.js";
import { plural } from "./format.js";
import { back, shoppingAvailable } from "./recipe.js";
import { currentRoute, href } from "./routes.js";

const view = () => document.getElementById("indkoebskurv");

// Linket på forsiden viser, hvor mange varer der er i kurven. Uden indkøbsliste er der ingen kurv.
export async function showLink() {
  const link = document.getElementById("basket-link");
  if (!(await shoppingAvailable())) return;
  const basket = await fetch("api/indkoebskurv")
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null);
  const count = basket ? basket.linjer.length : 0;
  link.textContent = count ? `🛒 Indkøbskurv · ${plural(count, "vare", "varer")}` : "🛒 Indkøbskurv";
  link.hidden = false;
}

function recipes(basket) {
  const remove = async (recipe) => {
    const updated = await send(`api/indkoebskurv/opskrifter/${encodeURIComponent(recipe.id)}`, { method: "DELETE" }, "Opskriften kunne ikke fjernes fra kurven.");
    if (updated) render(updated);
  };
  return el(
    "section",
    { class: "basket-recipes" },
    el("h2", {}, "Opskrifter"),
    ...basket.opskrifter.map((recipe) =>
      el(
        "div",
        { class: "trash-row" },
        el("a", { class: "row-t", href: href.recipe(recipe.id) }, recipe.titel),
        el("div", { class: "row-s" }, [recipe.portioner && plural(recipe.portioner, "portion", "portioner"), plural(recipe.antal, "ingrediens", "ingredienser")].filter(Boolean).join(" · ")),
        el("div", { class: "trash-actions" }, action("Fjern fra kurven", () => remove(recipe))),
      ),
    ),
  );
}

// Varerne med flueben. Fjern fluebenet ved det, husstanden har i forvejen. Varer uden mængde, fx "peber", er fravalgt fra start.
function items(basket) {
  const boxes = [];
  const submit = el("button", { type: "submit", class: "save" });
  const update = () => {
    const count = boxes.filter((box) => box.checked).length;
    submit.textContent = count ? `Send ${plural(count, "vare", "varer")} til indkøbslisten` : "Vælg varer";
    submit.disabled = count === 0;
  };
  const lines = basket.linjer.map((line) => {
    const box = el("input", { type: "checkbox", value: line.noegle, onchange: update });
    box.checked = line.har_maengde;
    boxes.push(box);
    return el("label", { class: "shop-line" }, box, el("span", {}, line.tekst, el("small", { class: "shop-for" }, `Til ${line.opskrifter.join(", ")}`)));
  });
  const sendAll = async (event) => {
    event.preventDefault();
    submit.disabled = true;
    const noegler = boxes.filter((box) => box.checked).map((box) => box.value);
    const result = await send("api/indkoebskurv/send", json("POST", { noegler }), "Varerne kunne ikke lægges på indkøbslisten.");
    if (!result) return update();
    toast(`${plural(result.antal, "vare er", "varer er")} lagt på indkøbslisten, og kurven er tømt.`);
    show();
  };
  const empty = async () => {
    const updated = await send("api/indkoebskurv", { method: "DELETE" }, "Kurven kunne ikke tømmes.");
    if (updated) render(updated);
  };
  update();
  return el(
    "form",
    { class: "shop-panel", onsubmit: sendAll },
    el("h2", {}, "Varer"),
    el("p", { class: "hint" }, "Ens ingredienser er lagt sammen. Fjern fluebenet ved det, I har i forvejen."),
    ...lines,
    el("div", { class: "shop-actions" }, submit),
    el("nav", { class: "tools" }, action("Tøm kurven", empty)),
  );
}

function render(basket) {
  const title = el("h1", { class: "title" }, "Indkøbskurv");
  if (!basket.opskrifter.length) {
    view().replaceChildren(back(), title, el("p", { class: "empty" }, "Kurven er tom. Læg ingredienser i kurven fra en opskrift."));
    return;
  }
  view().replaceChildren(back(), title, recipes(basket), items(basket));
}

export async function show() {
  view().replaceChildren(back(), el("h1", { class: "title" }, "Indkøbskurv"));
  const basket = await send("api/indkoebskurv", {}, "Kurven kunne ikke hentes. Prøv igen om lidt.");
  if (basket && currentRoute().view === "indkoebskurv") render(basket);
}
