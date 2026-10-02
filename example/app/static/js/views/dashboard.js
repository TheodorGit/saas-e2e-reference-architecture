import { get } from "../api.js";
import { fmt, h } from "../ui.js";

const PANELS = [
  ["credits", "Credit balance"],
  ["contacts", "Contacts"],
  ["subscribed", "Subscribed"],
  ["batches_sent", "Email batches sent"],
];

// Deliberate: each label renders at once, its number only when the data arrives.
export async function dashboardView(root) {
  const values = {};
  const grid = h("div", { class: "panels" }, PANELS.map(([key, label]) => {
    values[key] = h("div", { class: "panel-value", "data-testid": `value-${key}` }, "\u2014");
    return h("section", { class: "panel", "aria-label": label, "data-testid": `panel-${key}` },
      h("div", { class: "panel-label", text: label }), values[key]);
  }));
  root.append(h("h1", { text: "Dashboard" }), grid);

  const data = await get("/api/dashboard");
  for (const [key] of PANELS) {
    values[key].textContent = fmt(data[key]);
  }
}
