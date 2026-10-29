// Redigér en gemt opskrift i samme opsætning som gennemsynet, med originalbillederne fastgjort ved siden af.
import { action, el, json, pickImages, send, toast } from "./dom.js";
import { draftEditor, editable, originalsPanel, saveBox, toDraft } from "./editor.js";
import { go, href } from "./routes.js";

const recipeUrl = (id) => `api/opskrifter/${encodeURIComponent(id)}`;

export async function show(id) {
  const view = document.getElementById("rediger");
  view.replaceChildren();
  const recipe = await send(recipeUrl(id), {}, "Opskriften findes ikke.");
  if (!recipe) return go(href.library);
  // En fil med advarsel kan kun rettes via Samba.
  if (recipe.advarsel) return go(href.recipe(id));
  document.title = `Redigér ${recipe.titel} · Opskrifter`;
  const model = editable(recipe);
  let editor = null;

  const images = el("div", { class: "review-side" });
  const renderImages = (originals) => {
    const add = () =>
      pickImages({ multiple: true }, async (files) => {
        const body = new FormData();
        for (const file of files) body.append("billeder", file);
        toast("Gemmer originalbillederne …");
        const updated = await send(`${recipeUrl(id)}/originalbilleder`, { method: "POST", body }, "Billederne kunne ikke gemmes. Prøv igen.");
        if (!updated) return;
        toast("Originalbillederne er tilføjet.");
        renderImages(updated.originalbilleder);
      });
    images.replaceChildren(originalsPanel(originals), el("p", { class: "add-originals" }, action("+ Tilføj originalbilleder", add)));
  };
  renderImages(recipe.originalbilleder);

  const box = saveBox({
    label: "Gem ændringer",
    exceptId: id,
    onSave: async (anyway) => {
      const response = await fetch(recipeUrl(id), json("PUT", { udkast: toDraft(model), gem_alligevel: anyway }));
      const result = await response.json().catch(() => null);
      if (response.status === 409 && result && result.lignende) return result;
      if (!response.ok) return toast((result && result.detail) || "Ændringerne kunne ikke gemmes. Prøv igen."), null;
      toast("Ændringerne er gemt.");
      go(href.recipe(id));
      return null;
    },
    onCancel: () => editor.focusTitle(),
    extra: [el("a", { href: href.recipe(id), class: "discard" }, "Annullér redigering")],
  });

  editor = draftEditor(model, {
    kicker: `Redigér · ${id}.md`,
    hint: "Ret direkte i teksten. Filnavnet bevares, også hvis du ændrer titlen.",
    onChange: () => {},
    onTitle: (title) => box.check(title),
  });

  view.replaceChildren(
    el(
      "div",
      { class: "review" },
      images,
      el("article", { class: "review-draft" }, el("a", { class: "back", href: href.recipe(id) }, "← Opskriften"), editor.element, box.element),
    ),
  );
}
