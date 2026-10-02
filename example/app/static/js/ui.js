// Small DOM helpers and the app's shared widgets.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

export const fmt = (n) => Number(n).toLocaleString("en-US");

export function when(iso) {
  return iso ? new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC" : "";
}

export function toast(message, kind = "info") {
  const el = h("div", { class: `toast ${kind}`, text: message });
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), 6000);
  return el;
}

export function setToast(el, message, kind) {
  el.textContent = message;
  el.className = `toast ${kind}`;
}

// Deliberate: the icon word is part of the button's accessible name ("delete Delete").
export function iconButton(icon, label, attrs = {}) {
  return h("button", { type: "button", ...attrs }, h("span", { class: "icon", text: icon }),
    label ? " " + label : "");
}

// Deliberate: updates change the badge's text in place, never the element.
export function badge(status) {
  const el = h("span", { class: "badge", "data-testid": "status-badge" });
  const update = (value) => {
    el.textContent = value.charAt(0).toUpperCase() + value.slice(1);
    el.className = `badge badge-${value}`;
  };
  update(status);
  return { el, update };
}

// Deliberate: no ARIA roles, so role-based locators cannot find it.
export function dropdown({ placeholder, options = [], value = "", onChange, testid }) {
  let current = value;
  const toggle = h("div", { class: "dropdown-toggle", tabindex: "0" });
  const menu = h("div", { class: "dropdown-menu", hidden: true });
  const root = h("div", { class: "dropdown", "data-testid": testid }, toggle, menu);

  const label = () => {
    toggle.textContent = current || placeholder;
  };
  const choose = (option) => {
    current = option;
    menu.hidden = true;
    label();
    onChange?.(current);
  };
  const setOptions = (list) => {
    menu.replaceChildren(
      h("div", { class: "dropdown-item", onclick: () => choose("") }, placeholder),
      ...list.map((opt) => h("div", { class: "dropdown-item", onclick: () => choose(opt) }, opt)),
    );
  };
  toggle.addEventListener("click", () => { menu.hidden = !menu.hidden; });
  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) menu.hidden = true;
  });
  setOptions(options);
  label();
  return { el: root, setOptions, get value() { return current; } };
}

export function confirmDialog({ title, message, confirmIcon, confirmLabel }) {
  return new Promise((resolve) => {
    const close = (answer) => { backdrop.remove(); resolve(answer); };
    const dialog = h("div", { class: "dialog", role: "dialog", "aria-modal": "true",
      "aria-label": title },
      h("h2", { text: title }),
      h("p", { text: message }),
      h("div", { class: "actions" },
        h("button", { type: "button", onclick: () => close(false) }, "Cancel"),
        iconButton(confirmIcon, confirmLabel, { class: "danger", onclick: () => close(true) })));
    const backdrop = h("div", { class: "backdrop" }, dialog);
    document.body.append(backdrop);
  });
}

export function table(headers, rows, attrs = {}) {
  return h("table", attrs,
    h("thead", {}, h("tr", {}, headers.map((t) => h("th", { scope: "col", text: t })))),
    h("tbody", {}, rows));
}
