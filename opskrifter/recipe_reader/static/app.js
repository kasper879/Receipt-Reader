// Indgangen til frontenden: tema og navigation mellem skærmene. Skærmene ligger i js/.
import * as basket from "./js/basket.js";
import * as edit from "./js/edit.js";
import * as library from "./js/library.js";
import * as recipe from "./js/recipe.js";
import * as review from "./js/review.js";
import { currentRoute } from "./js/routes.js";
import * as trash from "./js/trash.js";
import { closeViewer } from "./js/viewer.js";

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

const VIEWS = {
  forside: () => (library.show(), basket.showLink()),
  opskrift: (id) => recipe.show(id),
  papirkurv: () => trash.show(),
  indkoebskurv: () => basket.show(),
  ny: () => review.showNew(),
  gennemsyn: (id) => review.showReview(id),
  rediger: (id) => edit.show(id),
};

async function route() {
  closeViewer();
  await review.flushDraft();
  let { view, id } = currentRoute();
  if (!VIEWS[view]) view = "forside";
  for (const section of document.querySelectorAll("[data-view]")) section.hidden = section.dataset.view !== view;
  window.scrollTo(0, 0);
  document.title = "Opskrifter";
  VIEWS[view](id);
}

followHaTheme();
document.addEventListener("visibilitychange", followHaTheme);
window.addEventListener("focus", followHaTheme);
window.addEventListener("hashchange", route);
document.getElementById("new-recipe").addEventListener("click", review.newRecipe);
window.addEventListener("pagehide", review.flushDraft);
route();
