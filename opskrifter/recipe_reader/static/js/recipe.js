// Opskriftsvisningen: hele opskriften på én side i kogebogsopsætningen, uden faner.
import { action, el, joined, json, pickImages, present, send, toast } from "./dom.js";
import { amount, duration, formatDate } from "./format.js";
import { currentRoute, go, href } from "./routes.js";
import { openViewer } from "./viewer.js";

const view = () => document.getElementById("opskrift");
const recipeUrl = (id) => `api/opskrifter/${encodeURIComponent(id)}`;

export const back = () => el("a", { class: "back", href: href.library }, "← Biblioteket");

const missing = () => el("b", { class: "nil" }, "—");

const fact = (label, value) => el("div", {}, el("span", {}, label), value);

function ingredients(recipe, factor) {
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
  );
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
    recipe.kilde && ["Fra ", el("i", {}, recipe.kilde)],
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
      el("div", { class: "body" }, ingredients(recipe, factor), steps(recipe)),
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
