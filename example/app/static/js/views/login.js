import { post } from "../api.js";
import { setSignedIn } from "../app.js";
import { h } from "../ui.js";

export function loginView(root) {
  const email = h("input", { id: "login-email", type: "email", autocomplete: "username",
    required: true });
  const password = h("input", { id: "login-password", type: "password",
    autocomplete: "current-password", required: true });
  const error = h("p", { class: "error", role: "alert" });
  const button = h("button", { type: "submit", class: "primary" }, "Sign in");

  const form = h("form", {
    class: "card narrow",
    onsubmit: async (event) => {
      event.preventDefault();
      error.textContent = "";
      button.disabled = true;
      try {
        await post("/api/login", { email: email.value, password: password.value });
        setSignedIn(true);
        location.hash = "#/dashboard";
      } catch (exc) {
        error.textContent = exc.message;
      } finally {
        button.disabled = false;
      }
    },
  },
  h("h1", { text: "Sign in to Demo ESP App" }),
  h("label", { for: "login-email" }, "Email"), email,
  h("label", { for: "login-password" }, "Password"), password,
  error, button);
  root.append(form);
}
