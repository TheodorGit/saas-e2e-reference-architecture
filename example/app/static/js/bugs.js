// The app's active defect switches (DEMO_ESP_BUGS), read once at start-up.
let active = [];

export async function loadBugs() {
  const response = await fetch("/api/flags");
  active = response.ok ? (await response.json()).bugs : [];
}

export const bug = (name) => active.includes(name);
