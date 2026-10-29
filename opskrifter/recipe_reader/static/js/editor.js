// Redigering af et udkast direkte i opskriftsopsætningen. Bruges af gennemsynet og ved redigering af en gemt opskrift.
//
// Ingredienser redigeres som tekstlinjer, én pr. ingrediens. De sendes som tekst til API'et,
// der tolker dem med samme parser som filformatet.
import { action, el, present, toast } from "./dom.js";
import { formatDate, ingredientLine } from "./format.js";
import { openViewer } from "./viewer.js";

// Et udkast fra API'et som redigerbar model: ingredienser som tekstlinjer.
export function editable(draft) {
  return {
    titel: draft.titel || "",
    portioner: draft.portioner,
    forberedelse: draft.forberedelse,
    total: draft.total,
    tags: [...(draft.tags || [])],
    kilde: draft.kilde || "",
    ingredienser: (draft.ingredienser || []).map((group) => ({
      gruppe: group.gruppe || "",
      linjer: group.linjer.map((line) => (typeof line === "string" ? line : ingredientLine(line))),
    })),
    trin: [...(draft.trin || [])],
    noter: draft.noter || "",
  };
}

// Modellen som udkast til API'et. Tomme felter er null.
export function toDraft(model) {
  const text = (value) => value.trim() || null;
  return {
    titel: text(model.titel),
    portioner: model.portioner,
    forberedelse: model.forberedelse,
    total: model.total,
    tags: model.tags.map((tag) => tag.trim()).filter(Boolean),
    kilde: text(model.kilde),
    ingredienser: model.ingredienser
      .map((group) => ({ gruppe: text(group.gruppe), linjer: group.linjer.map((line) => line.trim()).filter(Boolean) }))
      .filter((group) => group.gruppe || group.linjer.length),
    trin: model.trin.map((step) => step.trim()).filter(Boolean),
    noter: text(model.noter),
  };
}

function placeCaretAtEnd(node) {
  node.focus();
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(false);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

// Et felt, der rettes direkte i teksten. Tomme felter viser en kursiv pladsholder.
function text(tag, value, placeholder, onInput, { key, multiline = false, onKey, ...attrs } = {}) {
  const node = el(tag, { ...attrs, ...(key && { "data-key": key }), contenteditable: "plaintext-only", spellcheck: "true", "data-ph": placeholder });
  node.textContent = value;
  node.addEventListener("input", () => {
    // Et felt, der er tømt, skal være helt tomt, så pladsholderen vises igen.
    if (!node.textContent.trim() && node.childNodes.length) node.replaceChildren();
    onInput(multiline ? node.innerText.replace(/\n+$/, "") : node.textContent.replace(/\s*\n\s*/g, " "));
  });
  node.addEventListener("keydown", (event) => {
    if (onKey && onKey(event, node)) return event.preventDefault();
    if (event.key === "Enter" && !multiline) event.preventDefault();
  });
  node.addEventListener("paste", (event) => {
    if (multiline) return;
    event.preventDefault();
    document.execCommand("insertText", false, event.clipboardData.getData("text/plain").replace(/\s*\n\s*/g, " "));
  });
  return node;
}

function number(value, label, onInput) {
  const input = el("input", { class: "num", type: "number", inputmode: "numeric", min: "0", step: "1", placeholder: "Tilføj", "aria-label": label });
  if (value != null) input.value = value;
  input.addEventListener("input", () => {
    const parsed = parseInt(input.value, 10);
    onInput(Number.isFinite(parsed) && parsed >= 0 ? parsed : null);
  });
  return input;
}

const removeButton = (label, onclick) => el("button", { type: "button", class: "remove", "aria-label": label, title: label, onclick }, "×");

// Udkastet i opskriftsopsætningen. `onChange` kaldes ved hver rettelse, `onTitle` når titlen ændres.
export function draftEditor(model, { kicker, hint, top = [], onChange, onTitle }) {
  const root = el("div", { class: "draft" });

  function changed() {
    onChange(model);
  }

  // Tilføjer eller fjerner linjer og tegner udkastet igen med markøren i feltet `focus`.
  function rebuild(focus) {
    changed();
    render();
    const node = focus && root.querySelector(`[data-key="${focus}"]`);
    if (node) placeCaretAtEnd(node);
  }

  // Enter giver en ny linje efter den aktuelle. Backspace i en tom linje fjerner den.
  const listKeys = (list, i, keyOf, previousKey) => (event, node) => {
    if (event.key === "Enter" && !event.shiftKey) {
      list.splice(i + 1, 0, "");
      rebuild(keyOf(i + 1));
      return true;
    }
    if (event.key === "Backspace" && !node.textContent && list.length > 1) {
      list.splice(i, 1);
      rebuild(i > 0 ? keyOf(i - 1) : previousKey);
      return true;
    }
    return false;
  };

  function group(g, gi) {
    const lines = g.linjer.map((line, li) =>
      el(
        "li",
        {},
        text("span", line, "Tilføj ingrediens, fx 2 spsk karry", (value) => ((g.linjer[li] = value), changed()), {
          key: `ing-${gi}-${li}`,
          class: "line",
          onKey: listKeys(g.linjer, li, (i) => `ing-${gi}-${i}`, `group-${gi}`),
        }),
        removeButton("Fjern ingrediens", () => (g.linjer.splice(li, 1), rebuild())),
      ),
    );
    return el(
      "div",
      { class: "group" },
      el(
        "div",
        { class: "group-head" },
        text("h3", g.gruppe, model.ingredienser.length > 1 ? "Tilføj gruppe, fx Til sovsen" : "Gruppe (valgfri)", (value) => ((g.gruppe = value), changed()), {
          key: `group-${gi}`,
        }),
        model.ingredienser.length > 1 && removeButton("Fjern gruppen", () => (model.ingredienser.splice(gi, 1), rebuild())),
      ),
      el("ul", {}, ...lines),
      action("+ Ingrediens", () => (g.linjer.push(""), rebuild(`ing-${gi}-${g.linjer.length - 1}`)), { class: "add" }),
    );
  }

  function render() {
    if (!model.ingredienser.length) model.ingredienser.push({ gruppe: "", linjer: [""] });
    const steps = model.trin.map((step, i) =>
      el(
        "li",
        {},
        text("span", step, "Tilføj trin", (value) => ((model.trin[i] = value), changed()), {
          key: `step-${i}`,
          onKey: listKeys(model.trin, i, (n) => `step-${n}`, null),
        }),
        removeButton("Fjern trin", () => (model.trin.splice(i, 1), rebuild())),
      ),
    );
    root.replaceChildren(
      ...present([
        el("div", { class: "kicker" }, kicker),
        ...top,
        text("h1", model.titel, "Tilføj titel", (value) => ((model.titel = value), changed(), onTitle(value)), { key: "title", class: "title" }),
        hint && el("p", { class: "hint" }, hint),
        el(
          "div",
          { class: "facts" },
          el("div", {}, el("span", {}, "Portioner"), number(model.portioner, "Portioner", (v) => ((model.portioner = v || null), changed()))),
          el("div", {}, el("span", {}, "Forberedelse (min)"), number(model.forberedelse, "Forberedelse i minutter", (v) => ((model.forberedelse = v), changed()))),
          el("div", {}, el("span", {}, "I alt (min)"), number(model.total, "Samlet tid i minutter", (v) => ((model.total = v), changed()))),
        ),
        el(
          "div",
          { class: "body" },
          el(
            "aside",
            { class: "ings" },
            el("h2", {}, "Ingredienser"),
            ...model.ingredienser.map(group),
            action("+ Gruppe", () => (model.ingredienser.push({ gruppe: "", linjer: [""] }), rebuild(`group-${model.ingredienser.length - 1}`)), { class: "add" }),
          ),
          el(
            "section",
            { class: "steps" },
            el("h2", {}, "Fremgangsmåde"),
            el("ol", {}, ...steps),
            action("+ Trin", () => (model.trin.push(""), rebuild(`step-${model.trin.length - 1}`)), { class: "add" }),
            text("div", model.noter, "Tilføj en note, fx et tip fra originalen", (value) => ((model.noter = value), changed()), {
              key: "notes",
              class: "margin-note",
              multiline: true,
            }),
          ),
        ),
        el(
          "div",
          { class: "metaedit" },
          el("div", {}, "Kilde: ", text("span", model.kilde, "Tilføj kilde", (value) => ((model.kilde = value), changed()), { key: "source" })),
          el(
            "div",
            {},
            "Tags: ",
            text("span", model.tags.join(", "), "Tilføj tags adskilt med komma", (value) => ((model.tags = value.split(",")), changed()), { key: "tags" }),
          ),
        ),
      ]),
    );
  }

  render();
  return { element: root, focusTitle: () => placeCaretAtEnd(root.querySelector('[data-key="title"]')) };
}

// Originalbilledet, fastgjort øverst på telefonen og i venstre kolonne på desktop. Klik åbner stor visning.
export function originalsPanel(images) {
  let index = 0;
  const panel = el("div", { class: "review-img" });
  function render() {
    const pages =
      images.length > 1 &&
      el(
        "div",
        { class: "pager" },
        ...images.map((_, i) =>
          el("button", { type: "button", class: i === index ? "on" : "", onclick: () => ((index = i), render()) }, `Side ${i + 1}`),
        ),
      );
    panel.replaceChildren(
      ...present([
        images.length
          ? el(
              "button",
              { type: "button", class: "review-imgbox", "aria-label": "Åbn originalbilledet i stor visning", onclick: () => openViewer(images, index) },
              el("img", { src: images[index], alt: `Originalbillede ${index + 1} af ${images.length}` }),
            )
          : el("p", { class: "empty" }, "Ingen originalbilleder."),
        pages,
      ]),
    );
  }
  render();
  return panel;
}

// Gem-knappen. Ligner titlen en opskrift i biblioteket, erstattes den af en advarsel med "Gem alligevel" og "Annullér".
// `request(anyway)` sender gem-forespørgslen. Svarer API'et 409 med lignende titler, vises advarslen.
export function saveBox({ label, exceptId, request, onSaved, failure, onCancel, extra = [] }) {
  const box = el("div", { class: "savebox" });
  const slot = el("div", {});
  let similar = [];
  let timer = null;
  let titleCheck = 0;
  let saving = false;

  function render() {
    const button = el("button", { type: "button", class: "save", onclick: () => save(false) }, label);
    button.disabled = saving;
    if (!similar.length) return slot.replaceChildren(button);
    const [first] = similar;
    const added = first.oprettet ? ` Den blev tilføjet ${formatDate(first.oprettet)}.` : "";
    slot.replaceChildren(
      el(
        "div",
        { class: "dup", role: "alert" },
        el("b", {}, `Der findes allerede en opskrift, der hedder „${first.titel}“.`),
        added,
        el(
          "div",
          { class: "dup-actions" },
          el("button", { type: "button", class: "save", onclick: () => save(true) }, "Gem alligevel"),
          el("button", { type: "button", class: "secondary", onclick: onCancel }, "Annullér"),
        ),
      ),
    );
  }

  async function save(anyway) {
    if (saving) return;
    saving = true;
    render();
    try {
      const response = await request(anyway);
      const result = await response.json().catch(() => null);
      if (response.status === 409 && result && result.lignende) similar = result.lignende;
      else if (!response.ok) toast((result && typeof result.detail === "string" && result.detail) || failure);
      else onSaved(result);
    } catch {
      toast(failure);
    } finally {
      saving = false;
      render();
    }
  }

  // Advarslen opdateres, mens titlen skrives.
  function check(title) {
    clearTimeout(timer);
    // Et svar på en ældre titel ignoreres, så advarslen altid passer til titlen, som den står nu.
    const current = ++titleCheck;
    timer = setTimeout(async () => {
      const params = new URLSearchParams({ titel: title });
      if (exceptId) params.set("undtagen", exceptId);
      try {
        const response = await fetch(`api/lighed?${params}`);
        if (response.ok && current === titleCheck) {
          similar = await response.json();
          render();
        }
      } catch {
        // Lighedstjekket køres igen ved gem.
      }
    }, 250);
  }

  render();
  box.append(slot, ...extra);
  return { element: box, check };
}
