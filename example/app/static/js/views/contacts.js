import { del, get, post } from "../api.js";
import { bug } from "../bugs.js";
import { badge, confirmDialog, debounce, dropdown, h, iconButton, setToast, toast } from "../ui.js";

const SEARCH_DEBOUNCE_MS = 400;

export async function contactsView(root) {
  const selected = new Set();
  const rowsById = new Map();
  let request = 0;

  const search = h("input", { id: "contact-search", type: "search",
    placeholder: "Search by name or email" });
  const tagFilter = dropdown({ placeholder: "All tags", testid: "tag-filter",
    onChange: () => reload() });
  const exportLink = h("a", { class: "button", href: "/api/contacts/export" }, "Export CSV");
  const count = h("p", { class: "muted", "data-testid": "contacts-count" });
  // Deliberate: the list reloads only after typing pauses.
  search.addEventListener("input", debounce(() => reload(), SEARCH_DEBOUNCE_MS));

  const fields = {
    email: h("input", { id: "new-email", type: "email", required: true }),
    first_name: h("input", { id: "new-first" }),
    last_name: h("input", { id: "new-last" }),
    tags: h("input", { id: "new-tags", placeholder: "comma separated" }),
  };
  const addForm = h("form", { class: "card", hidden: true, "aria-label": "Add contact",
    onsubmit: async (event) => {
      event.preventDefault();
      const swap = bug("contact_names_swapped");
      const body = {
        email: fields.email.value,
        first_name: (swap ? fields.last_name : fields.first_name).value,
        last_name: (swap ? fields.first_name : fields.last_name).value,
        tags: fields.tags.value.split(",").map((t) => t.trim()).filter(Boolean),
      };
      // Deliberate: the confirmation shows before the request finishes.
      const note = toast("Contact saved", "success");
      addForm.hidden = true;
      try {
        await post("/api/contacts", body);
        for (const input of Object.values(fields)) input.value = "";
        await reload();
      } catch (exc) {
        setToast(note, `Could not save contact: ${exc.message}`, "error");
        addForm.hidden = false;
      }
    } },
  h("label", { for: "new-email" }, "Email"), fields.email,
  h("label", { for: "new-first" }, "First name"), fields.first_name,
  h("label", { for: "new-last" }, "Last name"), fields.last_name,
  h("label", { for: "new-tags" }, "Tags"), fields.tags,
  h("div", { class: "actions" },
    h("button", { type: "button", onclick: () => { addForm.hidden = true; } }, "Cancel"),
    h("button", { type: "submit", class: "primary" }, "Save contact")));
  const addButton = iconButton("person_add", "Add contact", { class: "primary",
    onclick: () => { addForm.hidden = false; fields.email.focus(); } });

  const bulkTag = h("input", { id: "bulk-tag" });
  const selectedCount = h("span", { "data-testid": "selected-count" });
  const bulkBar = h("div", { class: "bulkbar", hidden: true },
    selectedCount,
    h("label", { for: "bulk-tag" }, "Tag for selected"), bulkTag,
    h("button", { type: "button", onclick: () => bulk("add") }, "Add tag"),
    h("button", { type: "button", onclick: () => bulk("remove") }, "Remove tag"));

  async function bulk(action) {
    const tag = bulkTag.value.trim();
    if (!tag || !selected.size) return;
    const ids = [...selected];
    // Deliberate: rows change optimistically, then are re-read from the server.
    for (const id of ids) rowsById.get(id)?.optimistic(action, tag);
    try {
      const result = await post("/api/contacts/bulk-tag", { ids, tag, action });
      toast(`${action === "add" ? "Tagged" : "Untagged"} ${result.selected} contact(s)`,
        "success");
    } catch (exc) {
      toast(`Bulk ${action} failed: ${exc.message}`, "error");
    }
    if (bug("no_list_refresh")) return;
    await reload();
  }

  const body = h("tbody");
  const listTable = h("table", { "aria-label": "Contacts" },
    h("thead", {}, h("tr", {}, ["", "Email", "Name", "Status", "Tags", ""].map((t) =>
      h("th", { scope: "col", text: t })))), body);

  function chip(tag, pending) {
    return h("span", { class: pending ? "chip pending" : "chip", "data-testid": "tag-chip" },
      tag);
  }

  function row(contact) {
    const box = h("input", { type: "checkbox", id: `select-${contact.id}`,
      checked: selected.has(contact.id),
      onchange: () => {
        box.checked ? selected.add(contact.id) : selected.delete(contact.id);
        syncBulkBar();
      } });
    const tagCell = h("td", {}, contact.tags.map((t) => chip(t, false)));
    const status = badge(contact.status);
    const tr = h("tr", { "data-testid": "contact-row", "data-email": contact.email },
      h("td", {}, box, h("label", { for: `select-${contact.id}`, class: "sr-only" },
        `Select ${contact.email}`)),
      h("td", { text: contact.email }),
      h("td", { text: `${contact.first_name} ${contact.last_name}`.trim() }),
      h("td", {}, status.el),
      tagCell,
      h("td", {}, iconButton("delete", "Delete", { class: "danger small",
        onclick: () => remove(contact) })));
    rowsById.set(contact.id, {
      optimistic(action, tag) {
        const chips = [...tagCell.children];
        if (action === "add" && !chips.some((c) => c.textContent === tag)) {
          tagCell.append(chip(tag, true));
        }
        if (action === "remove") {
          chips.filter((c) => c.textContent === tag).forEach((c) => c.classList.add("pending"));
        }
      },
    });
    return tr;
  }

  async function remove(contact) {
    const ok = await confirmDialog({ title: "Delete contact",
      message: `Delete ${contact.email}? This cannot be undone.`,
      confirmIcon: "delete", confirmLabel: "Delete contact" });
    if (!ok) return;
    try {
      await del(`/api/contacts/${contact.id}`);
      selected.delete(contact.id);
      toast(`Deleted ${contact.email}`, "success");
    } catch (exc) {
      toast(`Could not delete: ${exc.message}`, "error");
    }
    await reload();
  }

  function syncBulkBar() {
    bulkBar.hidden = selected.size === 0;
    selectedCount.textContent = `${selected.size} selected`;
  }

  function filters() {
    const params = new URLSearchParams();
    if (search.value.trim()) params.set("q", search.value.trim());
    if (tagFilter.value) params.set("tag", tagFilter.value);
    return params.toString();
  }

  async function reload() {
    const mine = ++request;
    const query = filters();
    exportLink.href = `/api/contacts/export${query ? "?" + query : ""}`;
    listTable.setAttribute("aria-busy", "true");
    const [data, tags] = await Promise.all([get(`/api/contacts?${query}`), get("/api/tags")]);
    if (mine !== request) return;  // a newer search superseded this one
    rowsById.clear();
    body.replaceChildren(...data.items.map(row));
    tagFilter.setOptions(tags);
    for (const id of [...selected]) if (!data.items.some((c) => c.id === id)) selected.delete(id);
    count.textContent = `Showing ${data.count} contact${data.count === 1 ? "" : "s"}`;
    syncBulkBar();
    listTable.removeAttribute("aria-busy");
  }

  root.append(
    h("div", { class: "heading" }, h("h1", { text: "Contacts" }), addButton),
    addForm,
    h("div", { class: "toolbar" },
      h("label", { for: "contact-search", class: "sr-only" }, "Search contacts"), search,
      tagFilter.el, exportLink),
    bulkBar, count, listTable);
  await reload();
}
