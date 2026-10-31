// Opskriftsvisningen: hele opskriften på én side i kogebogsopsætningen, uden faner.
import { action, el, joined, json, pickImages, present, send, toast } from "./dom.js";
import { amount, duration, formatDate, plural } from "./format.js";
import { currentRoute, go, href } from "./routes.js";
import { openViewer } from "./viewer.js";

const view = () => document.getElementById("opskrift");
const recipeUrl = (id) => `api/opskrifter/${encodeURIComponent(id)}`;

export const back = () => el("a", { class: "back", href: href.library }, "← Biblioteket");

const missing = () => el("b", { class: "nil" }, "—");

const fact = (label, value) => el("div", {}, el("span", {}, label), value);

function ingredients(recipe, portions, factor) {
  return el(
    "aside",
    { class: "ings" },
    el("h2", {}, "Ingredienser"),
    ...recipe.ingredienser.flatMap((group) => [
      group.gruppe && el("h3", {}, group.gruppe),
      el(
        "ul",
        {},
        ...group.linjer.map((line) => {
          const quantity = amount(line, factor);
          return el("li", {}, quantity && el("span", { class: "q" }, quantity), quantity && " ", line.navn);
        }),
      ),
    ]),
    recipe.ingredienser.length > 0 && shoppingButton(recipe, portions, factor),
  );
}

// ---------------- Indkøbskurven ----------------

let shoppingStatus = null;

// Om der er en indkøbsliste i Home Assistant. Spørges kun én gang. Uden den er der heller ingen kurv.
export function shoppingAvailable() {
  shoppingStatus ??= fetch("api/indkoebsliste")
    .then((response) => (response.ok ? response.json() : null))
    .then((status) => Boolean(status && status.tilgaengelig), () => false);
  return shoppingStatus;
}

// Ting som vand, olie og salt under "Fra eget køkken" har husstanden som regel i forvejen.
const fromOwnKitchen = (group) => /eget køkken/i.test(group.gruppe || "");

// Ingredienserne med flueben, omregnet til de valgte portioner. Ingredienser uden mængde, fx "salt og peber",
// og ingredienser fra eget køkken er fravalgt fra start.
function shoppingPanel(recipe, portions, factor, close) {
  const chosen = [];
  const submit = el("button", { type: "submit", class: "save" });
  const update = () => {
    const count = chosen.filter(({ box }) => box.checked).length;
    submit.textContent = count ? `Læg ${plural(count, "vare", "varer")} i kurven` : "Vælg ingredienser";
    submit.disabled = count === 0;
  };
  const groups = recipe.ingredienser.flatMap((group) => [
    group.gruppe && el("h3", {}, group.gruppe),
    ...group.linjer.map((line) => {
      const box = el("input", { type: "checkbox", onchange: update });
      box.checked = line.maengde != null && !fromOwnKitchen(group);
      chosen.push({ box, line });
      return el("label", { class: "shop-line" }, box, " ", [amount(line, factor), line.navn].filter(Boolean).join(" "));
    }),
  ]);
  const add = async (event) => {
    event.preventDefault();
    submit.disabled = true;
    const varer = chosen
      .filter(({ box }) => box.checked)
      .map(({ line }) => ({ maengde: line.maengde == null ? null : line.maengde * factor, enhed: line.enhed, navn: line.navn }));
    const body = { portioner: recipe.portioner ? portions : null, varer };
    const basket = await send(`api/indkoebskurv/opskrifter/${encodeURIComponent(recipe.id)}`, json("PUT", body), "Varerne kunne ikke lægges i kurven.");
    if (basket) {
      toast(`„${recipe.titel}“ ligger i kurven. Der er ${plural(basket.linjer.length, "vare", "varer")} i alt.`);
      close();
    } else update();
  };
  update();
  return el(
    "form",
    { class: "shop-panel", onsubmit: add },
    el("p", { class: "hint" }, "Vælg det, du skal købe. Mængderne passer til de valgte portioner. Ligger opskriften allerede i kurven, erstattes den."),
    ...present(groups),
    el("div", { class: "shop-actions" }, submit, el("button", { type: "button", class: "secondary", onclick: close }, "Annullér")),
  );
}

function shoppingButton(recipe, portions, factor) {
  const slot = el("div", { class: "shop" });
  const closed = () =>
    slot.replaceChildren(
      el("button", { type: "button", class: "secondary", onclick: opened }, "🛒 Læg i indkøbskurven"),
      el("a", { class: "shop-basket", href: href.basket }, "Se kurven →"),
    );
  const opened = () => slot.replaceChildren(shoppingPanel(recipe, portions, factor, closed));
  shoppingAvailable().then((available) => available && closed());
  return slot;
}

function steps(recipe) {
  return el(
    "section",
    { class: "steps" },
    el("h2", {}, "Fremgangsmåde"),
    el("ol", {}, ...recipe.trin.map((step) => el("li", {}, el("span", {}, step)))),
    recipe.noter && el("div", { class: "margin-note" }, recipe.noter),
  );
}

function hero(recipe) {
  const image = recipe.retbillede || recipe.originalbilleder[0];
  if (!image) return null;
  const count = recipe.originalbilleder.length;
  return el(
    "figure",
    { class: "hero" },
    el("img", { src: image, alt: recipe.retbillede ? recipe.titel : "Originalbillede" }),
    el(
      "figcaption",
      {},
      recipe.retbillede ? "Retbillede" : "Intet retbillede endnu – viser originalbilledet",
      ...(count > 0 ? [" · ", action(`Se originalbilleder (${count})`, () => openViewer(recipe.originalbilleder))] : []),
    ),
  );
}

function portionStepper(recipe, portions) {
  const change = (delta) => () => render(recipe, Math.max(1, portions + delta));
  const less = el("button", { type: "button", "aria-label": "Færre portioner", onclick: change(-1) }, "−");
  less.disabled = portions <= 1;
  return el(
    "b",
    { class: "stepper" },
    less,
    String(portions),
    el("button", { type: "button", "aria-label": "Flere portioner", onclick: change(1) }, "+"),
  );
}

// Fælles vurdering for husstanden. Et klik på den aktuelle vurdering fjerner den.
function ratingControl(recipe, portions) {
  const rate = async (rating) => {
    const updated = await send(`${recipeUrl(recipe.id)}/vurdering`, json("PUT", { vurdering: rating }), "Vurderingen kunne ikke gemmes. Prøv igen.");
    if (updated) render(updated, portions);
  };
  const buttons = [1, 2, 3, 4, 5].map((i) =>
    el(
      "button",
      {
        type: "button",
        class: i <= (recipe.vurdering || 0) ? "on" : "",
        "aria-label": `${i} ${i === 1 ? "stjerne" : "stjerner"}`,
        onclick: () => rate(i === recipe.vurdering ? null : i),
      },
      "★",
    ),
  );
  return el(
    "div",
    { class: "rating" },
    el("span", { class: "stars", role: "group", "aria-label": recipe.vurdering ? `Vurdering: ${recipe.vurdering} af 5` : "Ingen vurdering" }, ...buttons),
    recipe.vurdering && action("fjern", () => rate(null), { class: "unrate" }),
  );
}

async function trash(recipe) {
  const result = await send(recipeUrl(recipe.id), { method: "DELETE" }, "Opskriften kunne ikke slettes. Prøv igen.");
  if (!result) return;
  toast(`„${recipe.titel}“ ligger nu i papirkurven, hvor den kan hentes tilbage.`);
  go(href.library);
}

function tools(recipe, portions) {
  const photoUrl = `${recipeUrl(recipe.id)}/retbillede`;
  const refresh = (updated) => updated && render(updated, portions);
  const upload = async ([file]) => {
    const body = new FormData();
    body.append("billede", file);
    toast("Gemmer retbilledet …");
    const updated = await send(photoUrl, { method: "PUT", body }, "Retbilledet kunne ikke gemmes. Prøv igen.");
    if (updated) toast("Retbilledet er gemt.");
    refresh(updated);
  };
  // Kameraet og galleriet har hver sin handling, fordi nogle telefoner ikke tilbyder kameraet i filvælgeren.
  const take = action("📷 Tag retbillede", () => pickImages({ camera: true }, upload));
  const choose = action(recipe.retbillede ? "Vælg et andet retbillede" : "Vælg retbillede", () => pickImages({}, upload));
  const remove = async () => refresh(await send(photoUrl, { method: "DELETE" }, "Retbilledet kunne ikke fjernes. Prøv igen."));
  const photo = recipe.retbillede ? [take, choose, action("Fjern retbillede", remove)] : [take, choose];
  const editLink = el("a", { href: href.edit(recipe.id) }, "Redigér");
  return el("nav", { class: "tools" }, ...joined([editLink, ...photo, action("Slet", () => trash(recipe))]));
}

function renderWarning(recipe) {
  // Appen overskriver aldrig en fil med advarsel. Den kan kun rettes via Samba, men den kan slettes til papirkurven.
  view().replaceChildren(
    back(),
    el("h1", { class: "title" }, recipe.titel),
    el("div", { class: "byline" }, `${recipe.id}.md`),
    el(
      "div",
      { class: "erratum" },
      el("b", {}, "Denne fil kunne ikke læses korrekt."),
      el("p", {}, recipe.advarsel),
      el("p", {}, "Ret filen via Samba, så vises opskriften her."),
    ),
    el("pre", { class: "raw" }, recipe.raa),
    el("nav", { class: "tools" }, action("Slet", () => trash(recipe))),
  );
}

function render(recipe, portions) {
  if (recipe.advarsel) return renderWarning(recipe);
  const factor = recipe.portioner ? portions / recipe.portioner : 1;
  const byline = [
    (recipe.kilde || recipe.link) && [
      "Fra ",
      recipe.link
        ? el("a", { href: recipe.link, target: "_blank", rel: "noopener" }, recipe.kilde || new URL(recipe.link).hostname)
        : el("i", {}, recipe.kilde),
    ],
    recipe.oprettet && [`tilføjet ${formatDate(recipe.oprettet)}`],
  ].filter(Boolean);
  view().replaceChildren(
    ...present([
      back(),
      recipe.tags.length > 0 && el("div", { class: "kicker" }, recipe.tags.join(" · ")),
      el("h1", { class: "title" }, recipe.titel),
      byline.length > 0 && el("div", { class: "byline" }, ...byline.flatMap((part, i) => (i ? [" · ", ...part] : part))),
      ratingControl(recipe, portions),
      hero(recipe),
      el(
        "div",
        { class: "facts" },
        fact("Portioner", recipe.portioner ? portionStepper(recipe, portions) : missing()),
        fact("Forberedelse", recipe.forberedelse ? el("b", {}, duration(recipe.forberedelse)) : missing()),
        fact("I alt", recipe.total ? el("b", {}, duration(recipe.total)) : missing()),
      ),
      el("div", { class: "body" }, ingredients(recipe, portions, factor), steps(recipe)),
      tools(recipe, portions),
    ]),
  );
}

export async function show(id) {
  view().replaceChildren();
  const stillShown = () => currentRoute().id === id;
  try {
    const response = await fetch(recipeUrl(id));
    if (response.status === 404) throw new Error("Opskriften findes ikke.");
    if (!response.ok) throw new Error("Opskriften kunne ikke hentes. Prøv igen om lidt.");
    const recipe = await response.json();
    if (!stillShown()) return;
    document.title = `${recipe.titel} · Opskrifter`;
    render(recipe, recipe.portioner);
  } catch (error) {
    if (stillShown()) view().replaceChildren(back(), el("p", { class: "empty" }, error.message));
  }
}
