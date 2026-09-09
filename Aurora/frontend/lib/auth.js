/**
 * Client-side auth: token storage and the signup/login/logout calls.
 *
 * The token is the only identity the client holds — the previous
 * localStorage-UUID "user id" is gone, since the server now derives the owner
 * from the JWT and ignores any client-supplied id.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const TOKEN_KEY = "aura_token";
const USER_KEY = "aura_user";

export function getToken() {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function persistSession({ access_token, user }) {
  try {
    localStorage.setItem(TOKEN_KEY, access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* private mode / storage disabled — session just won't survive a reload */
  }
  return user;
}

export function logout() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export function isLoggedIn() {
  return Boolean(getToken());
}

async function postAuth(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, res.status));
  }
  return persistSession(data);
}

export function signup({ email, password, displayName }) {
  return postAuth("/api/auth/signup", {
    email,
    password,
    display_name: displayName || null,
  });
}

export function login({ email, password }) {
  return postAuth("/api/auth/login", { email, password });
}

/**
 * FastAPI returns validation errors as `detail: [{msg, loc}, ...]` but simple
 * errors as `detail: "..."`. Flatten both into one readable string.
 */
function extractErrorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d.msg || "Invalid input").join(", ");
  }
  return `Request failed (${status})`;
}
