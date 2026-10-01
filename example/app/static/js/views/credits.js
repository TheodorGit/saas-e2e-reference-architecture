import { get } from "../api.js";
import { fmt, h, table, when } from "../ui.js";

export async function creditsView(root) {
  root.append(h("h1", { text: "Credits" }));
  const [credits, usage] = await Promise.all([get("/api/credits"), get("/api/usage")]);
  root.append(
    h("section", { class: "panel wide", "aria-label": "Credit balance" },
      h("div", { class: "panel-label", text: "Credit balance" }),
      h("div", { class: "panel-value", "data-testid": "credits-balance" }, fmt(credits.balance))),
    h("h2", { text: "Billing journal" }),
    h("p", { class: "muted", text: "One row per billable action." }),
    table(["When", "Action", "Reference", "Credits"], credits.journal.map((row) =>
      h("tr", { "data-testid": "journal-row" },
        h("td", { text: when(row.at) }), h("td", { text: row.action }),
        h("td", { text: row.reference }), h("td", { class: "num", text: fmt(row.credits) }))),
    { "aria-label": "Billing journal" }),
    h("h2", { text: "Usage log" }),
    h("p", { class: "muted", text: "Every action, billable or not, the moment it happened." }),
    table(["When", "Action", "Detail", "Credits"], usage.map((row) =>
      h("tr", { "data-testid": "usage-row" },
        h("td", { text: when(row.at) }), h("td", { text: row.action }),
        h("td", { text: row.detail }), h("td", { class: "num", text: fmt(row.credits) }))),
    { "aria-label": "Usage log" }));
}
