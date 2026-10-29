// Forsiden (biblioteket som tekstliste) og opskriftsvisningen. Visningen vælges med URL'ens hash
// (#opskrift/<id>), så alle URL'er er relative og appen virker under Ingress.
"use strict";

// Lys eller mørk tilstand følger HA, når appen vises i HA's Ingress-ramme, ellers systemet (via CSS).
function followHaTheme() {
  try {
    const ha = window.parent !== window && window.parent.document.querySelector("home-assistant");
    const dark = ha && ha.hass && ha.hass.themes && ha.hass.themes.darkMode;
    if (typeof dark === "boolean") document.documentElement.dataset.theme = dark ? "dark" : "light";
  } catch {
    // Ikke i HA, eller rammen er ikke tilgængelig: systemets indstilling gælder.
  }
}

// Udeladte børn (null, undefined og false) springes over.
const present = (children) => children.filter((child) => child != null && child !== false);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...present(children));
  return node;
}

const duration = (minutes) =>
  minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} t${minutes % 60 ? ` ${minutes % 60} min` : ""}`;

function stars(rating) {
  if (!rating) return null;
  const wrap = el("span", { class: "stars", "aria-label": `${rating} af 5 stjerner` });
  for (let i = 1; i <= 5; i++) wrap.append(el("span", { class: i <= rating ? "on" : "" }, "★"));
  return wrap;
}

function details(item) {
  if (item.advarsel) return ["Filen kunne ikke læses korrekt"];
  const parts = [];
  if (item.kilde) parts.push(el("i", {}, item.kilde));
  if (item.total) parts.push(duration(item.total));
  if (item.tags.length) parts.push(item.tags.join(", "));
  return parts.flatMap((part, i) => (i ? [" · ", part] : [part]));
}

function row(item) {
  const thumb = el("div", { class: "thumb" }, item.billede && el("img", { src: item.billede, alt: "", loading: "lazy" }));
  return el(
    "a",
    { class: "row", href: recipeHref(item.id) },
    thumb,
    el(
      "div",
      {},
      el("div", { class: "row-t" }, item.advarsel && el("span", { class: "warn" }, "⚠ "), item.titel),
      el("div", { class: "row-s" }, ...details(item)),
    ),
    el("div", { class: "row-r" }, stars(item.vurdering)),
  );
}

// Søgning, sortering og tagfilter. De bevares, når man går til en opskrift og tilbage.
const filters = { q: "", sortering: "nyeste", tag: null };

const SORTINGS = { nyeste: "nyeste først", vurdering: "højeste vurdering", alfabetisk: "alfabetisk" };

// Overskrifterne følger sorteringen: måned og år, forbogstav eller antal stjerner.
function heading(item) {
  if (filters.sortering === "alfabetisk") return item.titel.charAt(0).toUpperCase();
  if (filters.sortering === "vurdering") return item.vurdering ? "★".repeat(item.vurdering) : "Uden vurdering";
  if (!item.oprettet) return "Uden dato";
  const [year, month] = item.oprettet.split("-").map(Number);
  return `${MONTHS[month - 1]} ${year}`;
}

function sections(items) {
  let last = null;
  return items.flatMap((item) => {
    const title = heading(item);
    const parts = title === last ? [row(item)] : [el("h2", { class: "sec" }, title), row(item)];
    last = title;
    return parts;
  });
}

function link(label, on, onclick) {
  return el("a", { href: "", class: on ? "on" : "", onclick: (event) => (event.preventDefault(), onclick()) }, label);
}

const joined = (parts) => parts.flatMap((part, i) => (i ? [" · ", part] : [part]));

function controls(tags) {
  const sortLinks = Object.entries(SORTINGS).map(([key, label]) =>
    link(label, filters.sortering === key, () => ((filters.sortering = key), showLibrary())),
  );
  const tagLinks = [
    link("alle", !filters.tag, () => ((filters.tag = null), showLibrary())),
    ...tags.map((tag) => link(tag, filters.tag === tag, () => ((filters.tag = filters.tag === tag ? null : tag), showLibrary()))),
  ];
  return [
    el("div", {}, "Sortér: ", ...joined(sortLinks)),
    tags.length > 0 && el("div", {}, "Tags: ", ...joined(tagLinks)),
  ];
}

let libraryRequest = 0;
let libraryTotal = null;

async function showLibrary() {
  const request = ++libraryRequest;
  const lib = document.getElementById("lib");
  const params = new URLSearchParams({ q: filters.q, sortering: filters.sortering });
  if (filters.tag) params.set("tag", filters.tag);
  try {
    const [response, tagsResponse] = await Promise.all([fetch(`api/opskrifter?${params}`), fetch("api/tags")]);
    if (!response.ok || !tagsResponse.ok) throw new Error(response.statusText);
    const [items, tags] = await Promise.all([response.json(), tagsResponse.json()]);
    if (request !== libraryRequest) return;
    const filtered = filters.q.trim() || filters.tag;
    if (!filtered) libraryTotal = items.length;
    if (libraryTotal != null) {
      document.getElementById("kicker").textContent = `Biblioteket · ${libraryTotal} ${libraryTotal === 1 ? "opskrift" : "opskrifter"}`;
    }
    document.getElementById("controls").replaceChildren(...present(controls(tags)));
    const empty = filtered ? "Ingen opskrifter matcher søgningen." : "Biblioteket er tomt. Tilføj den første opskrift.";
    lib.replaceChildren(...(items.length ? sections(items) : [el("p", { class: "empty" }, empty)]));
  } catch {
    if (request === libraryRequest) lib.replaceChildren(el("p", { class: "empty" }, "Biblioteket kunne ikke hentes. Prøv igen om lidt."));
  }
}

let searchTimer = null;
document.querySelector(".search").addEventListener("input", (event) => {
  filters.q = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(showLibrary, 120);
});

// ---------------- Opskriftsvisning ----------------

const MONTHS = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december"];

function formatDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day}. ${MONTHS[month - 1]} ${year}`;
}

const FRACTIONS = [[1 / 4, "¼"], [1 / 3, "⅓"], [1 / 2, "½"], [2 / 3, "⅔"], [3 / 4, "¾"]];

function withFraction(value) {
  const whole = Math.floor(value);
  const fraction = FRACTIONS.find(([part]) => Math.abs(value - whole - part) < 0.01);
  return fraction && `${whole || ""}${fraction[1]}`;
}

// En omregnet mængde: brøkerne ¼, ⅓, ½, ⅔ og ¾, ellers én decimal med komma. Fra 20 og opefter heltal.
function formatQuantity(value) {
  if (value >= 20) return String(Math.round(value));
  return withFraction(value) || String(Math.max(0.1, Math.round(value * 10) / 10)).replace(".", ",");
}

// Omregningen gælder kun visningen og ændrer ikke filen. Uden omregning står mængden som i originalen,
// og ingredienser uden mængde står altid uændret.
function amount(line, factor) {
  if (line.maengde == null) return "";
  const quantity =
    factor === 1 ? withFraction(line.maengde) || String(line.maengde).replace(".", ",") : formatQuantity(line.maengde * factor);
  return [quantity, line.enhed].filter(Boolean).join(" ");
}

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
  const openOriginals = (event) => {
    event.preventDefault();
    openViewer(recipe.originalbilleder, 0);
  };
  return el(
    "figure",
    { class: "hero" },
    el("img", { src: image, alt: recipe.retbillede ? recipe.titel : "Originalbillede" }),
    el(
      "figcaption",
      {},
      recipe.retbillede ? "Retbillede" : "Intet retbillede endnu – viser originalbilledet",
      ...(count > 0 ? [" · ", el("a", { href: "", onclick: openOriginals }, `Se originalbilleder (${count})`)] : []),
    ),
  );
}

function portionStepper(recipe, portions) {
  const change = (delta) => () => renderRecipe(recipe, Math.max(1, portions + delta));
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

const back = () => el("a", { class: "back", href: "#" }, "← Biblioteket");

// Fælles vurdering for husstanden. Et klik på den aktuelle vurdering fjerner den.
function ratingControl(recipe, portions) {
  const rate = async (rating) => {
    const response = await fetch(`api/opskrifter/${encodeURIComponent(recipe.id)}/vurdering`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vurdering: rating }),
    });
    if (response.ok) renderRecipe(await response.json(), portions);
    else toast("Vurderingen kunne ikke gemmes. Prøv igen.");
  };
  const buttons = [1, 2, 3, 4, 5].map((i) =>
    el(
      "button",
      { type: "button", class: i <= (recipe.vurdering || 0) ? "on" : "", "aria-label": `${i} ${i === 1 ? "stjerne" : "stjerner"}`, onclick: () => rate(i === recipe.vurdering ? null : i) },
      "★",
    ),
  );
  return el(
    "div",
    { class: "rating" },
    el("span", { class: "stars", role: "group", "aria-label": recipe.vurdering ? `Vurdering: ${recipe.vurdering} af 5` : "Ingen vurdering" }, ...buttons),
    recipe.vurdering && el("a", { href: "", class: "unrate", onclick: (event) => (event.preventDefault(), rate(null)) }, "fjern"),
  );
}

let toastTimer = null;

function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.hidden = true), 3200);
}

function renderRecipe(recipe, portions) {
  const view = document.getElementById("opskrift");
  if (recipe.advarsel) {
    // Appen overskriver aldrig en fil med advarsel. Den kan kun rettes via Samba.
    view.replaceChildren(
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
    );
    return;
  }
  const factor = recipe.portioner ? portions / recipe.portioner : 1;
  const byline = [
    recipe.kilde && ["Fra ", el("i", {}, recipe.kilde)],
    recipe.oprettet && [`tilføjet ${formatDate(recipe.oprettet)}`],
  ].filter(Boolean);
  view.replaceChildren(...present([
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
  ]));
}

async function showRecipe(id) {
  const view = document.getElementById("opskrift");
  view.replaceChildren();
  const stillShown = () => shownRecipeId() === id;
  try {
    const response = await fetch(`api/opskrifter/${encodeURIComponent(id)}`);
    if (response.status === 404) throw new Error("Opskriften findes ikke.");
    if (!response.ok) throw new Error("Opskriften kunne ikke hentes. Prøv igen om lidt.");
    const recipe = await response.json();
    if (!stillShown()) return;
    document.title = `${recipe.titel} · Opskrifter`;
    renderRecipe(recipe, recipe.portioner);
  } catch (error) {
    if (stillShown()) view.replaceChildren(back(), el("p", { class: "empty" }, error.message));
  }
}

// ---------------- Stor visning af originalbilleder ----------------

let viewer = null;

function openViewer(images, index) {
  viewer = { images, index };
  renderViewer();
}

function closeViewer() {
  viewer = null;
  document.getElementById("viewer").hidden = true;
}

function moveViewer(delta) {
  const count = viewer.images.length;
  viewer.index = (viewer.index + delta + count) % count;
  renderViewer();
}

function renderViewer() {
  const { images, index } = viewer;
  const nav = images.length > 1 && [
    el("button", { type: "button", "aria-label": "Forrige billede", onclick: () => moveViewer(-1) }, "‹"),
    el("span", {}, `${index + 1} / ${images.length}`),
    el("button", { type: "button", "aria-label": "Næste billede", onclick: () => moveViewer(1) }, "›"),
  ];
  const box = document.getElementById("viewer");
  box.replaceChildren(
    el(
      "div",
      { class: "viewer-in", onclick: (event) => event.stopPropagation() },
      el("img", { src: images[index], alt: `Originalbillede ${index + 1} af ${images.length}` }),
      el("div", { class: "viewer-nav" }, ...(nav || []), el("button", { type: "button", onclick: closeViewer }, "Luk")),
    ),
  );
  box.hidden = false;
}

document.getElementById("viewer").addEventListener("click", closeViewer);
document.addEventListener("keydown", (event) => {
  if (!viewer) return;
  if (event.key === "Escape") closeViewer();
  if (event.key === "ArrowLeft") moveViewer(-1);
  if (event.key === "ArrowRight") moveViewer(1);
});

// ---------------- Navigation ----------------

const recipeHref = (id) => `#opskrift/${encodeURIComponent(id)}`;

// Id'et på opskriften i URL'en, eller null på forsiden.
function shownRecipeId() {
  const match = location.hash.match(/^#opskrift\/(.+)$/);
  return match && decodeURIComponent(match[1]);
}

function route() {
  closeViewer();
  const id = shownRecipeId();
  document.getElementById("forside").hidden = id != null;
  document.getElementById("opskrift").hidden = id == null;
  window.scrollTo(0, 0);
  document.title = "Opskrifter";
  if (id != null) showRecipe(id);
  else showLibrary();
}

followHaTheme();
document.addEventListener("visibilitychange", followHaTheme);
window.addEventListener("focus", followHaTheme);
window.addEventListener("hashchange", route);
route();
