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

// Vælg billeder med kamera eller fra galleriet. Telefonen tilbyder begge, når `capture` ikke er sat.
export function pickImages({ multiple }, onPicked) {
  const input = el("input", { type: "file", accept: "image/*", ...(multiple && { multiple: "" }) });
  input.addEventListener("change", () => input.files.length && onPicked([...input.files]));
  input.click();
}
