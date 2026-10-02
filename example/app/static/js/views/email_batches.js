import { get, post } from "../api.js";
import { badge, dropdown, fmt, h, iconButton, toast, when } from "../ui.js";

const POLL_MS = 1500;

// Deliberate: the list polls and changes each badge's text in place.
export async function emailBatchesView(root) {
  const rows = new Map();
  const body = h("tbody");

  function upsert(b) {
    const known = rows.get(b.id);
    if (known) {
      known.badge.update(b.status);
      known.recipients.textContent = b.status === "sent" ? fmt(b.recipients) : "";
      known.sent.textContent = when(b.sent_at);
      return;
    }
    const entry = { badge: badge(b.status), recipients: h("td", { class: "num" }),
      sent: h("td") };
    rows.set(b.id, entry);
    entry.recipients.textContent = b.status === "sent" ? fmt(b.recipients) : "";
    entry.sent.textContent = when(b.sent_at);
    body.prepend(h("tr", { "data-testid": "batch-row", "data-name": b.name },
      h("td", {}, h("a", { href: `#/email-batches/${b.id}` }, b.name)),
      h("td", { text: b.subject }),
      h("td", {}, entry.badge.el), entry.recipients, entry.sent));
  }

  async function refresh() {
    const list = await get("/api/email-batches");
    for (const b of [...list].reverse()) upsert(b);
  }

  root.append(
    h("div", { class: "heading" }, h("h1", { text: "Email batches" }),
      iconButton("add", "New email batch", { class: "primary",
        onclick: () => { location.hash = "#/email-batches/new"; } })),
    h("table", { "aria-label": "Email batches" },
      h("thead", {}, h("tr", {}, ["Name", "Subject", "Status", "Recipients", "Sent"].map(
        (t) => h("th", { scope: "col", text: t })))), body));
  await refresh();
  const timer = setInterval(() => refresh().catch(() => {}), POLL_MS);
  return () => clearInterval(timer);
}

export async function wizardView(root) {
  const [tags, lists] = await Promise.all([get("/api/tags"),
    get("/api/address-suppression-lists")]);
  const state = { audience: "all", tag: "", name: "", subject: "", body: "",
    suppression: new Set(), when: "now", sendAt: "" };
  const STEPS = ["Audience", "Message", "Address suppression", "Schedule"];
  let step = 0;

  const heading = h("h2");
  const panel = h("div", { class: "card" });
  const error = h("p", { class: "error", role: "alert" });
  const back = h("button", { type: "button", onclick: () => go(step - 1) }, "Back");
  const next = h("button", { type: "button", class: "primary", onclick: () => advance() },
    "Next");
  const send = h("button", { type: "button", class: "primary", onclick: () => submit() });

  const radio = (name, value, label, checked, onchange) => {
    const id = `${name}-${value}`;
    return h("div", { class: "choice" },
      h("input", { type: "radio", name, id, value, checked, onchange }),
      h("label", { for: id }, label));
  };

  const audienceTag = dropdown({ placeholder: "Choose a tag", options: tags,
    testid: "audience-tag", onChange: (t) => { state.tag = t; } });

  const screens = [
    () => [
      radio("audience", "all", "All subscribed contacts", state.audience === "all",
        () => { state.audience = "all"; }),
      radio("audience", "tag", "Subscribed contacts with a tag", state.audience === "tag",
        () => { state.audience = "tag"; }),
      audienceTag.el,
    ],
    () => {
      const input = (id, label, key, tag = "input") => {
        const el = h(tag, { id, value: state[key], rows: tag === "textarea" ? 8 : undefined,
          oninput: () => { state[key] = el.value; } });
        if (tag === "textarea") el.value = state[key];
        return [h("label", { for: id }, label), el];
      };
      return [
        ...input("b-name", "Email batch name", "name"),
        ...input("b-subject", "Subject", "subject"),
        ...input("b-body", "Message (HTML)", "body", "textarea"),
        h("p", { class: "muted", text: "Template variables: {{first_name}}, {{last_name}}, " +
          "{{email}}. " +
          "An unsubscribe header line and footer are added to every email." }),
      ];
    },
    () => lists.length ? lists.map((list) => {
      const id = `supp-${list.id}`;
      return h("div", { class: "choice" },
        h("input", { type: "checkbox", id, checked: state.suppression.has(list.id),
          onchange: (e) => e.target.checked ? state.suppression.add(list.id)
            : state.suppression.delete(list.id) }),
        h("label", { for: id }, `${list.name} (${list.size})`));
    }) : [h("p", { class: "muted", text: "No address suppression lists yet." })],
    () => {
      const at = h("input", { id: "b-send-at", type: "datetime-local", value: state.sendAt,
        oninput: () => { state.sendAt = at.value; } });
      const chosen = lists.filter((l) => state.suppression.has(l.id)).map((l) => l.name);
      return [
        radio("when", "now", "Send now", state.when === "now",
          () => { state.when = "now"; sync(); }),
        radio("when", "later", "Schedule for later", state.when === "later",
          () => { state.when = "later"; sync(); }),
        h("label", { for: "b-send-at" }, "Send at"), at,
        h("dl", { class: "review", "aria-label": "Review" },
          h("dt", { text: "Audience" }), h("dd", { text: state.audience === "tag"
            ? `Tag: ${state.tag}` : "All subscribed contacts" }),
          h("dt", { text: "Subject" }), h("dd", { text: state.subject }),
          h("dt", { text: "Address suppression" }),
          h("dd", { text: chosen.join(", ") || "None" })),
      ];
    },
  ];

  function validate() {
    if (step === 0 && state.audience === "tag" && !state.tag) return "Choose a tag.";
    if (step === 1 && !(state.name.trim() && state.subject.trim() && state.body.trim())) {
      return "Name, subject and message are all required.";
    }
    if (step === 3 && state.when === "later" && !state.sendAt) return "Choose when to send.";
    return "";
  }

  function sync() {
    send.textContent = state.when === "now" ? "Send email batch" : "Schedule email batch";
  }

  function go(to) {
    step = Math.max(0, Math.min(STEPS.length - 1, to));
    error.textContent = "";
    heading.textContent = `Step ${step + 1} of ${STEPS.length}: ${STEPS[step]}`;
    panel.replaceChildren(...screens[step]());
    back.hidden = step === 0;
    next.hidden = step === STEPS.length - 1;
    send.hidden = step !== STEPS.length - 1;
    sync();
  }

  function advance() {
    error.textContent = validate();
    if (!error.textContent) go(step + 1);
  }

  async function submit() {
    error.textContent = validate();
    if (error.textContent) return;
    send.disabled = true;
    try {
      const created = await post("/api/email-batches", {
        name: state.name, subject: state.subject, body_html: state.body,
        audience_tag: state.audience === "tag" ? state.tag : null,
        suppression_list_ids: [...state.suppression],
        send_at: state.when === "later" ? new Date(state.sendAt).toISOString() : null,
      });
      toast(`${created.name} is ${created.status}`, "success");
      location.hash = "#/email-batches";
    } catch (exc) {
      error.textContent = exc.message;
    } finally {
      send.disabled = false;
    }
  }

  root.append(h("h1", { text: "New email batch" }), heading, panel, error,
    h("div", { class: "actions" }, back, next, send));
  go(0);
}
