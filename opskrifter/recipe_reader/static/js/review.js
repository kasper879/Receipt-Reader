// Ny opskrift og gennemsyn: originalbilleder → aflæsning → udkast, der rettes og gemmes som opskrift.
import { action, el, imageButtons, joined, json, present, send, toast } from "./dom.js";
import { draftEditor, editable, originalsPanel, saveBox, toDraft } from "./editor.js";
import { plural } from "./format.js";
import { back } from "./recipe.js";
import { currentRoute, go, href } from "./routes.js";

const readingUrl = (id) => `api/aflaesninger/${encodeURIComponent(id)}`;

// ---------------- Ny opskrift: vælg billeder og send dem til aflæsning ----------------

let picked = [];

// "📷 Ny opskrift" åbner skærmen, hvor man tager billeder med kameraet eller vælger dem fra galleriet.
export function newRecipe() {
  go(href.newRecipe);
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
  const add = (files) => ((picked = [...picked, ...files]), showNew());
  const buttons = imageButtons(
    { cameraLabel: picked.length ? "Tag et billede mere" : "Tag billede", galleryLabel: "Vælg fra galleriet", multiple: true, className: "secondary" },
    add,
  );
  view.replaceChildren(
    ...present([
      back(),
      el("div", { class: "kicker" }, "Ny opskrift"),
      el("h1", { class: "title" }, "Billeder eller link"),
      el("p", { class: "hint" }, "Tag et billede af hver side, eller hent opskriften fra et link nedenfor. Fjern et billede, der ikke blev godt, før du sender billederne til aflæsning."),
      thumbs.length > 0 && el("div", { class: "picks" }, ...thumbs),
      el("div", { class: "pick-buttons" }, ...buttons),
      picked.length > 0 && el("button", { type: "button", class: "save", id: "read-button", onclick: read }, `Aflæs ${plural(picked.length, "billede", "billeder")}`),
      picked.length === 0 && linkForm(),
    ]),
  );
}

// Aflæsningen kører i baggrunden på serveren. Her ventes, til den er færdig, og der vises, hvor længe den har kørt.
export async function waitForReading(readingId, onTick = () => {}) {
  const started = Date.now();
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    onTick(Math.round((Date.now() - started) / 1000));
    const reading = await fetch(readingUrl(readingId)).then((r) => (r.ok ? r.json() : null), () => undefined);
    // undefined: ingen forbindelse lige nu, så der prøves igen. null: aflæsningen er kasseret.
    if (reading === null || (reading && !reading.i_gang)) return reading;
  }
}

// Fortæller, hvordan en færdig aflæsning gik, og går videre til gennemsynet eller forsiden.
export function afterReading(reading) {
  if (!reading) return go(href.library);
  if (reading.status === "ventende") {
    toast(
      reading.automatisk
        ? `Aflæsningen lykkedes ikke nu: ${reading.fejl} Billederne er gemt, og den prøves igen senere.`
        : `Billederne er gemt, men aflæsningen venter på dig: ${reading.fejl}`,
    );
    return go(href.library);
  }
  if (!reading.udkast.length) {
    toast(reading.fejl || "Aflæsningen fandt ingen opskrifter på billederne.");
    return go(href.library);
  }
  go(href.review(reading.id, reading.udkast[0].nr));
}

// Starter en aflæsning af billeder eller et link og viser, at den er i gang, til den er færdig.
async function startReading(url, options, { sending, failure, onStarted }) {
  const view = document.getElementById("ny");
  view.querySelectorAll("button, input").forEach((control) => (control.disabled = true));
  const status = el("span", {}, sending);
  view.append(el("div", { class: "reading", role: "status" }, el("span", { class: "spinner", "aria-hidden": "true" }), status));
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    response = null;
  }
  if (!response || response.status !== 202) {
    const detail = response && (await response.json().catch(() => null));
    toast((detail && typeof detail.detail === "string" && detail.detail) || failure);
    showNew();
    return;
  }
  onStarted();
  const started = await response.json();
  const leave = "Du kan godt forlade siden, så kommer resultatet på forsiden.";
  status.textContent = `Aflæser opskriften … Det tager typisk et halvt til et helt minut. ${leave}`;
  const reading = await waitForReading(started.id, (seconds) => (status.textContent = `Aflæser opskriften … ${seconds} s. ${leave}`));
  // Har brugeren forladt siden imens, vises resultatet som en note på forsiden i stedet.
  if (currentRoute().view === "ny") afterReading(reading);
}

function read() {
  const body = new FormData();
  for (const file of picked) body.append("billeder", file);
  startReading("api/aflaesninger", { method: "POST", body }, {
    sending: "Sender billederne …",
    failure: "Billederne kunne ikke sendes. Prøv igen.",
    onStarted: () => (picked = []),
  });
}

function readLink(link) {
  startReading("api/aflaesninger/link", json("POST", { link }), {
    sending: "Henter siden …",
    failure: "Linket kunne ikke bruges. Prøv igen.",
    onStarted: () => {},
  });
}

// Et link til en opskrift på en hjemmeside, i stedet for billeder.
function linkForm() {
  const input = el("input", { type: "url", class: "link-input", inputmode: "url", placeholder: "https://…", "aria-label": "Link til en opskrift" });
  const form = el(
    "form",
    {
      class: "link-form",
      onsubmit: (event) => {
        event.preventDefault();
        if (input.value.trim()) readLink(input.value.trim());
      },
    },
    el("label", { class: "kicker" }, "Eller hent fra et link"),
    el("div", { class: "link-row" }, input, el("button", { type: "submit", class: "secondary" }, "Hent opskrift")),
  );
  return form;
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
    top: [
      ...tabs(reading, draft.nr),
      // Et foto af retten på originalbillederne bliver automatisk retbillede, når udkastet gemmes.
      reading.link &&
        el(
          "p",
          { class: "hint dish-hint" },
          "Hentet fra ",
          el("a", { href: reading.link, target: "_blank", rel: "noopener" }, new URL(reading.link).hostname),
          reading.retbillede ? ". Billedet fra siden bliver opskriftens retbillede." : ".",
        ),
      draft.retbillede_omraade &&
        el(
          "p",
          { class: "hint dish-hint" },
          `📷 Fotoet af retten${reading.originalbilleder.length > 1 ? ` på side ${draft.retbillede_omraade.billede}` : ""} bliver opskriftens retbillede. Du kan skifte eller fjerne det, når opskriften er gemt.`,
        ),
    ],
    onChange: () => scheduleSave(reading.id, draft.nr, model),
    onTitle: (title) => box.check(title),
  });
  box.check(model.titel);

  view.replaceChildren(
    el(
      "div",
      { class: "review" },
      // Ved et link er der ingen originalbilleder. Så vises sidens billede af retten.
      originalsPanel(reading.originalbilleder.length ? reading.originalbilleder : [reading.retbillede].filter(Boolean)),
      el("article", { class: "review-draft" }, back(), editor.element, box.element),
    ),
  );
}
