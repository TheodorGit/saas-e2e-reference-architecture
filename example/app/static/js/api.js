// JSON calls to the app API; a 401 sends the user to the login screen.
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
  }
}

export async function api(method, path, body) {
  const options = { method, credentials: "same-origin", headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && path !== "/api/login") {
    location.hash = "#/login";
  }
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return data;
}

export const get = (path) => api("GET", path);
export const post = (path, body) => api("POST", path, body ?? {});
export const del = (path) => api("DELETE", path);
