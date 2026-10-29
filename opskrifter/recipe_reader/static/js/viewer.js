// Stor visning af originalbilleder, hvor man kan bladre mellem dem.
import { el } from "./dom.js";

let viewer = null;

export function openViewer(images, index = 0) {
  viewer = { images, index };
  render();
}

export function closeViewer() {
  viewer = null;
  document.getElementById("viewer").hidden = true;
}

function move(delta) {
  const count = viewer.images.length;
  viewer.index = (viewer.index + delta + count) % count;
  render();
}

function render() {
  const { images, index } = viewer;
  const nav = images.length > 1 && [
    el("button", { type: "button", "aria-label": "Forrige billede", onclick: () => move(-1) }, "‹"),
    el("span", {}, `${index + 1} / ${images.length}`),
    el("button", { type: "button", "aria-label": "Næste billede", onclick: () => move(1) }, "›"),
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
  if (event.key === "ArrowLeft") move(-1);
  if (event.key === "ArrowRight") move(1);
});
