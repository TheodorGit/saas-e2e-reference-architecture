import { get, post } from "../api.js";
import { h, table, toast } from "../ui.js";

const lines = (text) => text.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);

export async function suppressionView(root) {
  const name = h("input", { id: "list-name", required: true });
  const emails = h("textarea", { id: "list-emails", rows: 4 });
  const listTable = table(["Name", "Addresses", ""], [], { "aria-label": "Address suppression lists" });
  const body = listTable.tBodies[0];
  const detail = h("section", { class: "card", hidden: true, "data-testid": "list-detail" });

  const form = h("form", { class: "card", "aria-label": "New address suppression list",
    onsubmit: async (event) => {
      event.preventDefault();
      try {
        const created = await post("/api/address-suppression-lists",
          { name: name.value, emails: lines(emails.value) });
        toast(`Created ${created.name} with ${created.size} address(es)`, "success");
        name.value = "";
        emails.value = "";
        await reload();
      } catch (exc) {
        toast(`Could not create the list: ${exc.message}`, "error");
      }
    } },
  h("h2", { text: "New address suppression list" }),
  h("label", { for: "list-name" }, "List name"), name,
  h("label", { for: "list-emails" }, "Addresses (one per line)"), emails,
  h("button", { type: "submit", class: "primary" }, "Create list"));

  async function show(id) {
    const list = await get(`/api/address-suppression-lists/${id}`);
    const more = h("textarea", { id: "more-emails", rows: 3 });
    detail.hidden = false;
    detail.replaceChildren(
      h("h2", { text: list.name }),
      h("ul", { "aria-label": `Addresses in ${list.name}` },
        list.emails.map((e) => h("li", { text: e }))),
      h("label", { for: "more-emails" }, "Add addresses"), more,
      h("button", { type: "button", onclick: async () => {
        await post(`/api/address-suppression-lists/${id}/entries`, { emails: lines(more.value) });
        await Promise.all([show(id), reload()]);
      } }, "Add to list"));
  }

  async function reload() {
    const lists = await get("/api/address-suppression-lists");
    body.replaceChildren(...lists.map((list) => h("tr", { "data-testid": "suppression-row" },
      h("td", { text: list.name }), h("td", { class: "num", text: list.size }),
      h("td", {}, h("button", { type: "button", onclick: () => show(list.id) },
        `View ${list.name}`)))));
  }

  root.append(h("h1", { text: "Address suppression lists" }),
    h("p", { class: "muted", text: "Addresses on a selected list are never mailed." }),
    listTable, form, detail);
  await reload();
}
