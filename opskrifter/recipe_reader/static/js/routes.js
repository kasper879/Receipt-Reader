// Skærmen vælges med URL'ens hash, så alle URL'er er relative og appen virker under Ingress.

export const href = {
  library: "#",
  recipe: (id) => `#opskrift/${encodeURIComponent(id)}`,
  trash: "#papirkurv",
  newRecipe: "#ny",
  review: (readingId, nr) => `#gennemsyn/${encodeURIComponent(readingId)}/${nr}`,
  edit: (id) => `#rediger/${encodeURIComponent(id)}`,
};

// Den viste skærm og dens id, fx { view: "opskrift", id: "boller-i-karry" }.
export function currentRoute() {
  const [, view = "forside", id = null] = location.hash.match(/^#([^/]+)(?:\/(.+))?$/) || [];
  try {
    return { view, id: id && decodeURIComponent(id) };
  } catch {
    return { view, id };
  }
}

export const go = (target) => (location.hash = target);
