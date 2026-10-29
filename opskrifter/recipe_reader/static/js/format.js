// Visning af tider, datoer og mængder.

export const MONTHS = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december"];

export const duration = (minutes) =>
  minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} t${minutes % 60 ? ` ${minutes % 60} min` : ""}`;

export function formatDate(iso) {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return `${day}. ${MONTHS[month - 1]} ${year}`;
}

export function formatMonth(iso) {
  const [year, month] = iso.split("-").map(Number);
  return `${MONTHS[month - 1]} ${year}`;
}

export const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`;

const FRACTIONS = [[1 / 4, "¼"], [1 / 3, "⅓"], [1 / 2, "½"], [2 / 3, "⅔"], [3 / 4, "¾"]];

function withFraction(value) {
  const whole = Math.floor(value);
  const fraction = FRACTIONS.find(([part]) => Math.abs(value - whole - part) < 0.01);
  return fraction && `${whole || ""}${fraction[1]}`;
}

// En omregnet mængde: brøkerne ¼, ⅓, ½, ⅔ og ¾, ellers én decimal med komma. Fra 20 og opefter heltal.
function formatQuantity(value) {
  if (value >= 20) return String(Math.round(value));
  return withFraction(value) || String(Math.max(0.1, Math.round(value * 10) / 10)).replace(".", ",");
}

// Omregningen gælder kun visningen og ændrer ikke filen. Uden omregning står mængden som i originalen,
// og ingredienser uden mængde står altid uændret.
export function amount(line, factor = 1) {
  if (line.maengde == null) return "";
  const quantity =
    factor === 1 ? withFraction(line.maengde) || String(line.maengde).replace(".", ",") : formatQuantity(line.maengde * factor);
  return [quantity, line.enhed].filter(Boolean).join(" ");
}

// En ingrediens som tekstlinje, fx "2 spsk karry". Backenden tolker den igen med filformatets parser.
export const ingredientLine = (line) => [amount(line), line.navn].filter(Boolean).join(" ");
