import { post } from "../api.js";
import { h } from "../ui.js";

export function validateView(root) {
  const input = h("input", { id: "validate-email", type: "email", required: true,
    placeholder: "name@example.com" });
  const button = h("button", { type: "submit", class: "primary" }, "Validate address");
  const result = h("div", { class: "result", "data-testid": "validation-result", hidden: true });

  const form = h("form", {
    class: "card",
    onsubmit: async (event) => {
      event.preventDefault();
      button.disabled = true;
      result.hidden = true;
      try {
        const data = await post("/api/validate", { email: input.value });
        const charge = data.free
          ? "Free: this address was validated within the free window"
          : `Charged ${data.cost} credits`;
        result.className = `result verdict-${data.result}`;
        result.replaceChildren(
          h("p", { class: "verdict" }, `${data.email} is ${data.result}`),
          h("p", { class: "charge", "data-testid": "validation-charge" }, charge));
      } catch (exc) {
        result.className = "result error";
        result.replaceChildren(h("p", { role: "alert", text: exc.message }));
      } finally {
        result.hidden = false;
        button.disabled = false;
      }
    },
  },
  h("p", { class: "muted" },
    "Validate one address before you mail it. Each validation costs credits; validating " +
    "the same address again within the free window costs nothing."),
  h("label", { for: "validate-email" }, "Email address"), input, button);
  root.append(h("h1", { text: "Validate an address" }), form, result);
}
