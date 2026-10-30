// Forsiden: biblioteket som tekstliste med søgning, sortering og tags.
import { action, el, joined, present, send, toast } from "./dom.js";
import { duration, formatDate, formatMonth, plural } from "./format.js";
import { currentRoute, href } from "./routes.js";
import { afterReading, waitForReading } from "./review.js";

// Søgning, sortering og tagfilter. De bevares, når man går til en opskrift og tilbage.
const filters = { q: "", sortering: "nyeste", tag: null };

const SORTINGS = { nyeste: "nyeste først", vurdering: "højeste vurdering", alfabetisk: "alfabetisk" };

export function stars(rating) {
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
  return joined(parts);
}

function row(item) {
  const thumb = el("div", { class: "thumb" }, item.billede && el("img", { src: item.billede, alt: "", loading: "lazy" }));
  return el(
    "a",
    { class: "row", href: href.recipe(item.id) },
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

// Overskrifterne følger sorteringen: måned og år, forbogstav eller antal stjerner.
function heading(item) {
  if (filters.sortering === "alfabetisk") return item.titel.charAt(0).toUpperCase();
  if (filters.sortering === "vurdering") return item.vurdering ? "★".repeat(item.vurdering) : "Uden vurdering";
  return item.oprettet ? formatMonth(item.oprettet) : "Uden dato";
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
  return action(label, onclick, { class: on ? "on" : "" });
}

function controls(tags) {
  const sortLinks = Object.entries(SORTINGS).map(([key, label]) =>
    link(label, filters.sortering === key, () => ((filters.sortering = key), show())),
  );
  const tagLinks = [
    link("alle", !filters.tag, () => ((filters.tag = null), show())),
    ...tags.map((tag) => link(tag, filters.tag === tag, () => ((filters.tag = filters.tag === tag ? null : tag), show()))),
  ];
  return [el("div", {}, "Sortér: ", ...joined(sortLinks)), tags.length > 0 && el("div", {}, "Tags: ", ...joined(tagLinks))];
}

const readingUrl = (id) => `api/aflaesninger/${encodeURIComponent(id)}`;

function timeOf(iso) {
  const when = new Date(iso);
  const today = new Date().toDateString() === when.toDateString();
  const clock = when.toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit" });
  return today ? `i dag kl. ${clock}` : `${formatDate(iso)} kl. ${clock}`;
}

// Det, der aflæses: originalbilleder eller en side fra et link.
const what = (reading) =>
  reading.link
    ? `Opskriften fra ${new URL(reading.link).hostname}`
    : plural(reading.originalbilleder.length, "originalbillede", "originalbilleder");

// Noter om ventende aflæsninger og udkast, der ikke er gennemset endnu.
function note(reading) {
  if (reading.i_gang) {
    return el(
      "aside",
      { class: "note" },
      el("span", { class: "spinner inline", "aria-hidden": "true" }),
      el("b", {}, " Aflæser … "),
      `${what(reading)} fra ${timeOf(reading.oprettet)} bliver læst lige nu.`,
    );
  }
  if (reading.status === "ventende") {
    const retry = async () => {
      const started = await send(`${readingUrl(reading.id)}/proev-igen`, { method: "POST" }, "Aflæsningen kunne ikke prøves igen nu.");
      if (!started) return;
      showNotes();
      afterReading(await waitForReading(reading.id));
      showNotes();
    };
    const discard = async () => {
      if (await send(readingUrl(reading.id), { method: "DELETE" }, "Aflæsningen kunne ikke kasseres. Prøv igen.")) showNotes();
    };
    return el(
      "aside",
      { class: "note" },
      el("b", {}, "Ventende aflæsning. "),
      `${what(reading)} fra ${timeOf(reading.oprettet)} venter på at blive læst. `,
      // En ugyldig API-nøgle eller afviste billeder prøves ikke igen af sig selv. Så venter aflæsningen på brugeren.
      ...(reading.automatisk
        ? ["Det sker af sig selv, når der er forbindelse igen – eller ", action("prøv nu", retry), ". ", reading.fejl && el("span", { class: "note-reason" }, reading.fejl, " ")]
        : [el("span", { class: "note-reason" }, reading.fejl, " "), "Ret det, og ", action("prøv igen", retry), ". "]),
      action("Kassér billederne", discard, { class: "note-discard" }),
    );
  }
  if (!reading.udkast.length) {
    const discard = async () => {
      if (await send(readingUrl(reading.id), { method: "DELETE" }, "Aflæsningen kunne ikke kasseres. Prøv igen.")) showNotes();
    };
    return el("aside", { class: "note" }, el("b", {}, "Aflæsningen fandt ingen opskrifter "), `på billederne fra ${timeOf(reading.oprettet)}. `, action("Kassér billederne", discard));
  }
  const count = reading.udkast.length;
  return el(
    "aside",
    { class: "note" },
    el("b", {}, `${plural(count, "udkast", "udkast")} venter på gennemsyn. `),
    reading.udkast.map((draft) => draft.titel || "Uden titel").join(", "),
    ". ",
    el("a", { href: href.review(reading.id, reading.udkast[0].nr) }, "Fortsæt gennemsynet"),
  );
}

let notesTimer = null;

async function showNotes() {
  clearTimeout(notesTimer);
  const readings = await fetch("api/aflaesninger").then((r) => (r.ok ? r.json() : []), () => []);
  document.getElementById("notes").replaceChildren(...readings.map(note));
  // Mens en aflæsning kører, opdateres noten af sig selv, så resultatet kommer frem uden at genindlæse siden.
  if (readings.some((reading) => reading.i_gang) && currentRoute().view === "forside") notesTimer = setTimeout(showNotes, 3000);
}

let request = 0;
let total = null;

export async function show() {
  showNotes();
  const current = ++request;
  const lib = document.getElementById("lib");
  const params = new URLSearchParams({ q: filters.q, sortering: filters.sortering });
  if (filters.tag) params.set("tag", filters.tag);
  try {
    const [response, tagsResponse] = await Promise.all([fetch(`api/opskrifter?${params}`), fetch("api/tags")]);
    if (!response.ok || !tagsResponse.ok) throw new Error(response.statusText);
    const [items, tags] = await Promise.all([response.json(), tagsResponse.json()]);
    if (current !== request) return;
    const filtered = filters.q.trim() || filters.tag;
    if (!filtered) total = items.length;
    if (total != null) document.getElementById("kicker").textContent = `Biblioteket · ${plural(total, "opskrift", "opskrifter")}`;
    document.getElementById("controls").replaceChildren(...present(controls(tags)));
    const empty = filtered ? "Ingen opskrifter matcher søgningen." : "Biblioteket er tomt. Tilføj den første opskrift.";
    lib.replaceChildren(...(items.length ? sections(items) : [el("p", { class: "empty" }, empty)]));
  } catch {
    if (current === request) lib.replaceChildren(el("p", { class: "empty" }, "Biblioteket kunne ikke hentes. Prøv igen om lidt."));
  }
}

let searchTimer = null;
document.querySelector(".search").addEventListener("input", (event) => {
  filters.q = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(show, 120);
});
