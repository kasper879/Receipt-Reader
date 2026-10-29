// Små hjælpere til at bygge sider og tale med API'et. Alle URL'er er relative, så appen virker under Ingress.

// Udeladte børn (null, undefined og false) springes over.
export const present = (children) => children.filter((child) => child != null && child !== false);

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...present(children));
  return node;
}

export const joined = (parts) => parts.flatMap((part, i) => (i ? [" · ", part] : [part]));

// Et tekstlink, der udfører en handling i stedet for at navigere.
export function action(label, onclick, attrs = {}) {
  return el("a", { href: "", ...attrs, onclick: (event) => (event.preventDefault(), onclick()) }, label);
}

let toastTimer = null;

// En kort besked nederst på skærmen.
export function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.hidden = true), 3600);
}

// Kalder API'et og returnerer svaret som JSON. En fejl vises som en besked, og så returneres null.
export async function send(url, options, failure) {
  try {
    const response = await fetch(url, options);
    if (response.ok) return await response.json();
    const body = await response.json().catch(() => null);
    toast((body && typeof body.detail === "string" && body.detail) || failure);
  } catch {
    toast(failure);
  }
  return null;
}

export const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// Tag et billede med kameraet (`camera`) eller vælg billeder fra galleriet. Uden `capture` viser nogle
// telefoner, fx HA companion-appen på Android, kun filer og galleri, så kameraet har sin egen knap.
export function pickImages({ multiple = false, camera = false }, onPicked) {
  const input = el("input", {
    type: "file",
    accept: "image/*",
    hidden: "",
    ...(camera && { capture: "environment" }),
    ...(multiple && !camera && { multiple: "" }),
  });
  // Feltet hænges på siden, mens det bruges. Nogle WebViews sender ellers ikke besked om det valgte billede.
  document.body.append(input);
  input.addEventListener("change", () => {
    const files = [...input.files];
    input.remove();
    if (files.length) onPicked(files);
  });
  input.addEventListener("cancel", () => input.remove());
  input.click();
}

// To knapper: tag et billede med kameraet, eller vælg fra galleriet.
export function imageButtons({ cameraLabel, galleryLabel, multiple = false, className = "" }, onPicked) {
  return [
    el("button", { type: "button", class: className, onclick: () => pickImages({ camera: true }, onPicked) }, `📷 ${cameraLabel}`),
    el("button", { type: "button", class: className, onclick: () => pickImages({ multiple }, onPicked) }, `🖼 ${galleryLabel}`),
  ];
}
