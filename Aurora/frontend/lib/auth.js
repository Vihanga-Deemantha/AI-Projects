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

/**
 * Authenticated fetch for the profile/password endpoints below. This is a
 * separate (small, duplicated) helper rather than importing lib/api.js's
 * authFetch — that module already imports getToken/logout from THIS file,
 * so importing back would be a circular dependency.
 */
async function authFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: token ? { ...options.headers, Authorization: `Bearer ${token}` } : options.headers,
  });
  if (res.status === 401) {
    logout();
    throw new Error("Your session has expired. Please log in again.");
  }
  return res;
}

async function authFetchJson(path, options) {
  const res = await authFetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(extractErrorMessage(data, res.status));
  return data;
}

const USER_UPDATED_EVENT = "aura:user-updated";

/**
 * Updates the cached user in localStorage (e.g. after a profile edit or
 * avatar upload) and broadcasts it in-tab. The native "storage" event only
 * fires in OTHER tabs, so components like AppSidebar that cache their own
 * copy of the user (read once on mount) would otherwise go stale after an
 * edit made elsewhere on the same page.
 */
export function syncUser(updatedUser) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(updatedUser));
  } catch {
    /* private mode / storage disabled */
  }
  window.dispatchEvent(new CustomEvent(USER_UPDATED_EVENT, { detail: updatedUser }));
}

/** Subscribes to in-tab user updates from syncUser(). Returns an unsubscribe function. */
export function onUserUpdated(callback) {
  const handler = (e) => callback(e.detail);
  window.addEventListener(USER_UPDATED_EVENT, handler);
  return () => window.removeEventListener(USER_UPDATED_EVENT, handler);
}

/** Fetches the current user fresh from the server (not the cached localStorage copy). */
export async function getMe() {
  const user = await authFetchJson("/api/auth/me");
  syncUser(user);
  return user;
}

export async function updateProfile({ displayName, bio }) {
  const user = await authFetchJson("/api/auth/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName, bio }),
  });
  syncUser(user);
  return user;
}

export async function uploadAvatar(file) {
  const form = new FormData();
  form.set("file", file);
  const { avatar_url } = await authFetchJson("/api/auth/avatar", { method: "POST", body: form });
  const user = getStoredUser();
  if (user) syncUser({ ...user, avatar_url });
  return avatar_url;
}

export function changePassword({ currentPassword, newPassword }) {
  return authFetchJson("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export async function forgotPassword(email) {
  const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, res.status));
  }
}

export function verifyOTP({ email, otp, newPassword }) {
  return postAuth("/api/auth/verify-otp", { email, otp, new_password: newPassword });
}

/**
 * `link: true` requests "connect Google to my current account" rather than
 * a plain sign-in — the backend needs the caller's identity to do that
 * safely (so it can refuse a mismatched Google account instead of silently
 * switching the active session), and a top-level redirect can't carry an
 * Authorization header, so the token rides along as a query param instead.
 */
export function getGoogleAuthUrl({ link = false } = {}) {
  if (!link) return `${API_BASE}/api/auth/google`;
  const token = getToken();
  return `${API_BASE}/api/auth/google?link_token=${encodeURIComponent(token || "")}`;
}

export async function disconnectGoogle() {
  const user = await authFetchJson("/api/auth/google/disconnect", { method: "POST" });
  syncUser(user);
  return user;
}

/**
 * Parses ?token=...&user=...&next=... from the current URL (set by the
 * backend's Google OAuth redirect on success — failures redirect straight to
 * /login or /profile with ?error= instead of coming through here), persists
 * the session, and strips those params from the address bar. `next` is
 * "/practice" after a login/signup and "/profile" after linking Google to
 * an already-logged-in account. Returns { user: null, next } if the URL
 * doesn't carry a valid token/user.
 */
export function handleGoogleCallback() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  const userJson = params.get("user");
  const next = params.get("next") || "/practice";
  window.history.replaceState({}, "", window.location.pathname);

  if (!token || !userJson) return { user: null, next };
  try {
    return { user: persistSession({ access_token: token, user: JSON.parse(userJson) }), next };
  } catch {
    return { user: null, next };
  }
}
