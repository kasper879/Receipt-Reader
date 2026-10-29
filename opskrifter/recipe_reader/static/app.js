// Forsiden: biblioteket som tekstliste. Alle URL'er er relative, så appen virker under Ingress.
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

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  node.append(...children.filter((child) => child != null && child !== false));
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
    "div",
    { class: "row" },
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

async function showLibrary() {
  const lib = document.getElementById("lib");
  try {
    const response = await fetch("api/opskrifter");
    if (!response.ok) throw new Error(response.statusText);
    const items = await response.json();
    document.getElementById("kicker").textContent = `Biblioteket · ${items.length} ${items.length === 1 ? "opskrift" : "opskrifter"}`;
    lib.replaceChildren(
      ...(items.length ? items.map(row) : [el("p", { class: "empty" }, "Biblioteket er tomt. Tilføj den første opskrift.")]),
    );
  } catch {
    lib.replaceChildren(el("p", { class: "empty" }, "Biblioteket kunne ikke hentes. Prøv igen om lidt."));
  }
}

followHaTheme();
document.addEventListener("visibilitychange", followHaTheme);
window.addEventListener("focus", followHaTheme);
showLibrary();
