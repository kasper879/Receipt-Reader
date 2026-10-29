// Ny opskrift og gennemsyn: originalbilleder → aflæsning → udkast, der rettes og gemmes som opskrift.
import { action, el, joined, json, pickImages, present, send, toast } from "./dom.js";
import { draftEditor, editable, originalsPanel, saveBox, toDraft } from "./editor.js";
import { plural } from "./format.js";
import { back } from "./recipe.js";
import { go, href } from "./routes.js";

const readingUrl = (id) => `api/aflaesninger/${encodeURIComponent(id)}`;

// ---------------- Ny opskrift: vælg billeder og send dem til aflæsning ----------------

let picked = [];

// "📷 Ny opskrift" åbner kameraet eller billedgalleriet med det samme.
export function newRecipe() {
  pickImages({ multiple: true }, (files) => {
    picked = [...picked, ...files];
    go(href.newRecipe);
  });
}

export function showNew() {
  const view = document.getElementById("ny");
  const thumbs = picked.map((file, i) => {
    const url = URL.createObjectURL(file);
    return el(
      "div",
      { class: "pick" },
      el("img", { src: url, alt: `Billede ${i + 1}`, onload: () => URL.revokeObjectURL(url) }),
      el("button", { type: "button", class: "remove", "aria-label": "Fjern billedet", onclick: () => (picked.splice(i, 1), showNew()) }, "×"),
    );
  });
  const more = () => pickImages({ multiple: true }, (files) => ((picked = [...picked, ...files]), showNew()));
  view.replaceChildren(
    ...present([
      back(),
      el("div", { class: "kicker" }, "Ny opskrift"),
      el("h1", { class: "title" }, "Originalbilleder"),
      el("p", { class: "hint" }, "Tag et billede af hver side. Fjern et billede, der ikke blev godt, før du sender dem til aflæsning."),
      el("div", { class: "picks" }, ...thumbs, el("button", { type: "button", class: "pick add-pick", onclick: more }, picked.length ? "+ Flere billeder" : "📷 Tag eller vælg billeder")),
      picked.length > 0 && el("button", { type: "button", class: "save", id: "read-button", onclick: read }, `Aflæs ${plural(picked.length, "billede", "billeder")}`),
    ]),
  );
}

async function read() {
  const view = document.getElementById("ny");
  const body = new FormData();
  for (const file of picked) body.append("billeder", file);
  view.querySelectorAll("button").forEach((button) => (button.disabled = true));
  view.append(el("div", { class: "reading", role: "status" }, el("span", { class: "spinner", "aria-hidden": "true" }), "Aflæser opskriften … Det tager typisk et halvt minut."));
  let response;
  try {
    response = await fetch("api/aflaesninger", { method: "POST", body });
  } catch {
    response = null;
  }
  if (!response || (!response.ok && response.status !== 202)) {
    const detail = response && (await response.json().catch(() => null));
    toast((detail && typeof detail.detail === "string" && detail.detail) || "Billederne kunne ikke sendes. Prøv igen.");
    showNew();
    return;
  }
  picked = [];
  const reading = await response.json();
  if (reading.status === "ventende") {
    toast(
      reading.automatisk
        ? "Billederne er gemt. Aflæsningen kunne ikke gennemføres nu, så den prøves igen senere."
        : `Billederne er gemt, men aflæsningen venter på dig: ${reading.fejl}`,
    );
    go(href.library);
  } else {
    go(reading.udkast.length ? href.review(reading.id, reading.udkast[0].nr) : href.library);
    if (!reading.udkast.length) toast(reading.fejl || "Aflæsningen fandt ingen opskrifter på billederne.");
  }
}

// ---------------- Gennemsyn ----------------

let pendingSave = null;

// Rettelser gemmes midlertidigt, mens man redigerer, så de bevares ved skift af udkast og efter en genstart.
function scheduleSave(readingId, nr, model) {
  clearTimeout(pendingSave && pendingSave.timer);
  const run = () => {
    pendingSave = null;
    // keepalive, så rettelserne også når frem, når appen lukkes midt i gennemsynet.
    return fetch(`${readingUrl(readingId)}/udkast/${nr}`, { ...json("PUT", toDraft(model)), keepalive: true }).catch(() => null);
  };
  pendingSave = { run, timer: setTimeout(run, 700) };
}

// Gemmer ventende rettelser med det samme, fx før man skifter til et andet udkast.
export async function flushDraft() {
  if (!pendingSave) return;
  clearTimeout(pendingSave.timer);
  await pendingSave.run();
}

function tabs(reading, current) {
  if (reading.udkast.length < 2) return [];
  const links = reading.udkast.map((draft, i) =>
    el("a", { href: href.review(reading.id, draft.nr), class: draft.nr === current ? "on" : "" }, `${i + 1}. ${draft.titel || "Uden titel"}`),
  );
  return [el("p", { class: "hint" }, `Aflæsningen fandt ${reading.udkast.length} opskrifter på billederne. Gennemse dem én ad gangen.`), el("nav", { class: "drafttabs" }, ...joined(links))];
}

function next(readingId, following) {
  if (following != null) go(href.review(readingId, following));
  else go(href.library);
}

export async function showReview(id) {
  const view = document.getElementById("gennemsyn");
  const [readingId, nrText] = (id || "").split("/");
  view.replaceChildren();
  const reading = await send(readingUrl(readingId), {}, "Udkastet findes ikke længere.");
  if (!reading) return go(href.library);
  const nr = Number(nrText);
  const draft = reading.udkast.find((d) => d.nr === nr) || reading.udkast[0];
  if (!draft) return go(href.library);
  const model = editable(draft);
  let editor = null;

  const box = saveBox({
    label: "Gem i biblioteket",
    request: async (anyway) => {
      await flushDraft();
      return fetch(`${readingUrl(reading.id)}/udkast/${draft.nr}/gem`, json("POST", { udkast: toDraft(model), gem_alligevel: anyway }));
    },
    onSaved: (result) => {
      toast(`„${model.titel.trim() || result.id}“ er gemt i biblioteket.`);
      next(reading.id, result.naeste);
    },
    failure: "Opskriften kunne ikke gemmes. Prøv igen.",
    onCancel: () => editor.focusTitle(),
    extra: [
      action("Kassér dette udkast", async () => {
        clearTimeout(pendingSave && pendingSave.timer);
        pendingSave = null;
        const result = await send(`${readingUrl(reading.id)}/udkast/${draft.nr}`, { method: "DELETE" }, "Udkastet kunne ikke kasseres. Prøv igen.");
        if (!result) return;
        toast("Udkastet er kasseret.");
        next(reading.id, result.naeste);
      }, { class: "discard" }),
    ],
  });

  editor = draftEditor(model, {
    kicker: reading.udkast.length > 1 ? `Gennemsyn · aflæsningen fandt ${reading.udkast.length} opskrifter` : "Gennemsyn · udkast",
    hint: "Aflæsningen gætter ikke: Felter, der ikke stod i originalen, er tomme. Ret direkte i teksten, og udfyld det, du vil.",
    top: tabs(reading, draft.nr),
    onChange: () => scheduleSave(reading.id, draft.nr, model),
    onTitle: (title) => box.check(title),
  });
  box.check(model.titel);

  view.replaceChildren(
    el(
      "div",
      { class: "review" },
      originalsPanel(reading.originalbilleder),
      el("article", { class: "review-draft" }, back(), editor.element, box.element),
    ),
  );
}
