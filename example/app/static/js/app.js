// The shell: hash routing, sign-in state, and one view at a time.
import { get, post } from "./api.js";
import { loadBugs } from "./bugs.js";
import { contactsView } from "./views/contacts.js";
import { creditsView } from "./views/credits.js";
import { dashboardView } from "./views/dashboard.js";
import { emailBatchesView, wizardView } from "./views/email_batches.js";
import { loginView } from "./views/login.js";
import { reportView } from "./views/report.js";
import { suppressionView } from "./views/suppression.js";
import { validateView } from "./views/validate.js";

const routes = [
  [/^#\/login$/, loginView, false],
  [/^#\/dashboard$/, dashboardView, true],
  [/^#\/contacts$/, contactsView, true],
  [/^#\/validate$/, validateView, true],
  [/^#\/email-batches$/, emailBatchesView, true],
  [/^#\/email-batches\/new$/, wizardView, true],
  [/^#\/email-batches\/(\d+)$/, reportView, true],
  [/^#\/suppression$/, suppressionView, true],
  [/^#\/credits$/, creditsView, true],
];

let cleanup = null;
let signedIn = null;

async function isSignedIn() {
  if (signedIn === null) {
    signedIn = await get("/api/me").then(() => true, () => false);
  }
  return signedIn;
}

export function setSignedIn(value) {
  signedIn = value;
}

async function render() {
  const hash = location.hash || "#/dashboard";
  const match = routes.find(([pattern]) => pattern.test(hash));
  if (!match) {
    location.hash = "#/dashboard";
    return;
  }
  const [pattern, view, needsLogin] = match;
  if (needsLogin && !(await isSignedIn())) {
    location.hash = "#/login";
    return;
  }
  cleanup?.();
  cleanup = null;
  document.getElementById("topbar").hidden = !needsLogin;
  for (const link of document.querySelectorAll("nav a")) {
    link.toggleAttribute("aria-current", hash.startsWith(link.getAttribute("href")));
  }
  const root = document.getElementById("view");
  root.replaceChildren();
  cleanup = (await view(root, ...hash.match(pattern).slice(1))) || null;
}

document.getElementById("signout").addEventListener("click", async () => {
  await post("/api/logout");
  signedIn = false;
  location.hash = "#/login";
});

window.addEventListener("hashchange", render);
loadBugs().finally(render);
