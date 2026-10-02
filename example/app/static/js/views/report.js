import { get } from "../api.js";
import { badge, fmt, h, when } from "../ui.js";

const CARDS = [
  ["delivered", "Delivered", "delivered_to", "Delivered to"],
  ["opens", "Opens", "opened_by", "Opened by"],
  ["clicks", "Clicks", "clicked_by", "Clicked by"],
];

// Deliberate: cards paint label first, number later.
export async function reportView(root, id) {
  const title = h("h1", { text: "Email batch report" });
  const meta = h("p", { class: "muted" });
  const status = badge("loading");
  const drill = h("section", { class: "card", hidden: true, "data-testid": "drilldown" });
  const values = {};
  let data = null;

  const cards = h("div", { class: "panels" }, CARDS.map(([key, label, listKey, heading]) => {
    values[key] = h("span", { class: "panel-value", "data-testid": `card-value-${key}` },
      "\u2014");
    return h("button", { type: "button", class: "panel stat", "data-testid": `card-${key}`,
      onclick: () => showList(heading, listKey) },
    h("span", { class: "panel-label", text: label }), values[key]);
  }));

  function showList(heading, listKey) {
    if (!data) return;
    const people = data[listKey];
    drill.hidden = false;
    drill.replaceChildren(h("h2", { text: heading }),
      people.length ? h("ul", { "aria-label": heading }, people.map((e) => h("li", { text: e })))
        : h("p", { class: "muted", text: "Nobody yet." }));
  }

  async function load() {
    data = await get(`/api/email-batches/${id}/report`);
    title.textContent = data.batch.name;
    status.update(data.batch.status);
    meta.textContent = `Subject: ${data.batch.subject} \u00b7 sent ${
      when(data.batch.sent_at) || "not yet"} \u00b7 ${fmt(data.batch.recipients)} recipient(s)`;
    for (const [key] of CARDS) values[key].textContent = fmt(data[key]);
    drill.hidden = true;
  }

  root.append(title, h("p", {}, status.el), meta, cards,
    h("button", { type: "button", onclick: () => load() }, "Refresh report"), drill);
  await load();
}
