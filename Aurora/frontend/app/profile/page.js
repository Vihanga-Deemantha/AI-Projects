"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import AppSidebar from "@/components/AppSidebar";
import {
  changePassword,
  disconnectGoogle,
  getGoogleAuthUrl,
  getMe,
  updateProfile,
  uploadAvatar,
} from "@/lib/auth";

const GOOGLE_LINK_ERRORS = {
  google_not_configured: "Google sign-in isn't set up on this server yet.",
  google_link_mismatch: "That Google account's email doesn't match your AURA account. Sign out of Google and try again with the matching account.",
  google_link_conflict: "That Google account is already linked to a different AURA account.",
  google_failed: "Connecting Google didn't complete. Please try again.",
};

export default function ProfilePage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
        <AppSidebar />
        {/* useSearchParams() below (for a failed Google-link redirect) needs a Suspense boundary. */}
        <Suspense fallback={null}>
          <Profile />
        </Suspense>
      </div>
    </AuthGuard>
  );
}

function Profile() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [linkError, setLinkError] = useState(null);

  useEffect(() => {
    getMe()
      .then((u) => {
        setUser(u);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  // A failed "Connect Google" attempt redirects back here with ?error=...
  useEffect(() => {
    const code = searchParams.get("error");
    if (code) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from the URL after a server-side redirect, not derived from props/state
      setLinkError(GOOGLE_LINK_ERRORS[code] || "Something went wrong connecting Google.");
      router.replace("/profile");
    }
  }, [searchParams, router]);

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
      <header className="mb-7">
        <h1 className="font-display text-[28px] font-bold">Your Profile</h1>
        <p className="text-sm text-foreground/50">Manage your account details and sign-in options.</p>
      </header>

      {status === "loading" && <p className="text-sm text-foreground/40">Loading…</p>}
      {status === "error" && (
        <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-500">
          Couldn&apos;t load your profile. Try refreshing the page.
        </div>
      )}

      {status === "ready" && (
        <div className="flex flex-col gap-6">
          <AvatarCard user={user} onUpdated={setUser} />
          <PersonalInfoCard user={user} onUpdated={setUser} />
          <SecurityCard user={user} onUpdated={setUser} />
          <ConnectedAccountsCard user={user} onUpdated={setUser} linkError={linkError} />
        </div>
      )}
    </main>
  );
}

function Card({ title, children }) {
  return (
    <section className="rounded-2xl border border-panel-border bg-panel p-6">
      <h2 className="mb-5 font-display text-lg font-bold">{title}</h2>
      {children}
    </section>
  );
}

function AvatarCard({ user, onUpdated }) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const initial = (user.display_name || user.email || "A").charAt(0).toUpperCase();

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const avatar_url = await uploadAvatar(file);
      onUpdated({ ...user, avatar_url });
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <Card title="Avatar">
      <div className="flex items-center gap-5">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="group relative h-24 w-24 shrink-0 overflow-hidden rounded-full disabled:cursor-wait"
        >
          {user.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- avatar comes from an external Cloudinary/Google CDN, not a locally-optimizable asset
            <img src={user.avatar_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-linear-to-br from-sky-300 to-brand font-display text-3xl font-bold text-white">
              {initial}
            </div>
          )}
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 text-[11px] font-semibold text-white opacity-0 transition group-hover:opacity-100">
            {uploading ? "Uploading…" : "Change Photo"}
          </div>
          {uploading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            </div>
          )}
        </button>
        <div>
          <p className="text-sm font-medium">Click your photo to change it</p>
          <p className="mt-1 text-xs text-foreground/45">JPEG, PNG, or WebP — up to 5 MB.</p>
          {error && <p className="mt-1 text-xs text-rose-500">{error}</p>}
        </div>
        <input
          ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp"
          className="hidden" onChange={handleFileChange}
        />
      </div>
    </Card>
  );
}

function PersonalInfoCard({ user, onUpdated }) {
  const [displayName, setDisplayName] = useState(user.display_name || "");
  const [bio, setBio] = useState(user.bio || "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateProfile({ displayName, bio });
      onUpdated(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Personal Info">
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-2">
          <span className="text-[11px] font-bold uppercase tracking-wide text-foreground/40">Display Name</span>
          <input
            value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={100}
            className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
          />
        </label>
        <label className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wide text-foreground/40">Bio</span>
            <span className="text-[11px] text-foreground/35">{bio.length}/300</span>
          </div>
          <textarea
            value={bio} onChange={(e) => setBio(e.target.value.slice(0, 300))} rows={3}
            placeholder="Tell us a bit about your English learning goals."
            className="resize-none rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3 text-sm outline-none transition placeholder:text-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/15"
          />
        </label>

        {error && <p className="text-xs text-rose-500">{error}</p>}

        <div className="flex items-center gap-3">
          <button
            type="button" onClick={handleSave} disabled={saving}
            className="rounded-full bg-linear-to-br from-brand to-brand-dark px-5 py-2.5 font-display text-sm font-bold text-white shadow-md shadow-brand/20 transition hover:brightness-110 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
          {saved && <span className="text-sm font-medium text-emerald-500">Saved!</span>}
        </div>
      </div>
    </Card>
  );
}

function SecurityCard({ user, onUpdated }) {
  const [expanded, setExpanded] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (next.length < 8) return setError("New password must be at least 8 characters.");
    if (next !== confirm) return setError("Passwords don't match.");

    setSaving(true);
    try {
      await changePassword({ currentPassword: user.has_password ? current : undefined, newPassword: next });
      onUpdated({ ...user, has_password: true });
      setCurrent(""); setNext(""); setConfirm("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Security">
      <button
        type="button" onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between text-left text-sm font-medium text-foreground/70"
      >
        {user.has_password ? "Change Password" : "Set a Password"}
        <ChevronIcon className={`h-4 w-4 text-foreground/40 transition ${expanded ? "rotate-90" : ""}`} />
      </button>

      {expanded && (
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          {!user.has_password && (
            <p className="rounded-lg bg-brand-soft px-3 py-2 text-xs text-brand">
              Your account currently signs in with Google only. Set a password to also log in with email.
            </p>
          )}
          {user.has_password && (
            <input
              type="password" required value={current} onChange={(e) => setCurrent(e.target.value)}
              placeholder="Current password" autoComplete="current-password"
              className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
            />
          )}
          <input
            type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)}
            placeholder="New password" autoComplete="new-password"
            className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
          />
          <input
            type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
            placeholder="Confirm new password" autoComplete="new-password"
            className="rounded-[13px] border border-panel-border bg-foreground/5 px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
          />
          {error && <p className="text-xs text-rose-500">{error}</p>}
          <div className="flex items-center gap-3">
            <button
              type="submit" disabled={saving}
              className="rounded-full bg-linear-to-br from-brand to-brand-dark px-5 py-2.5 font-display text-sm font-bold text-white shadow-md shadow-brand/20 transition hover:brightness-110 disabled:opacity-50"
            >
              {saving ? "Saving…" : user.has_password ? "Update Password" : "Set Password"}
            </button>
            {saved && <span className="text-sm font-medium text-emerald-500">Updated!</span>}
          </div>
        </form>
      )}
    </Card>
  );
}

function ConnectedAccountsCard({ user, onUpdated, linkError }) {
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState(null);

  async function handleDisconnect() {
    setError(null);
    setDisconnecting(true);
    try {
      const updated = await disconnectGoogle();
      onUpdated(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setDisconnecting(false);
    }
  }

  const canDisconnect = user.google_linked && user.has_password;

  return (
    <Card title="Connected Accounts">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GoogleIcon className="h-5 w-5" />
          <div>
            <p className="text-sm font-medium">Google</p>
            <p className="text-xs text-foreground/45">
              {user.google_linked ? "Connected" : "Not connected"}
            </p>
          </div>
        </div>

        {user.google_linked ? (
          <button
            type="button"
            onClick={handleDisconnect}
            disabled={!canDisconnect || disconnecting}
            title={canDisconnect ? undefined : "Set a password before disconnecting Google"}
            className="rounded-full border border-panel-border px-4 py-2 text-xs font-semibold transition hover:border-rose-500/40 hover:text-rose-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {disconnecting ? "Disconnecting…" : "Disconnect"}
          </button>
        ) : (
          <a
            href={getGoogleAuthUrl({ link: true })}
            className="rounded-full border border-panel-border px-4 py-2 text-xs font-semibold transition hover:border-brand/40 hover:text-brand"
          >
            Connect
          </a>
        )}
      </div>
      {(error || linkError) && <p className="mt-2 text-xs text-rose-500">{error || linkError}</p>}
    </Card>
  );
}

function ChevronIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GoogleIcon(props) {
  return (
    <svg viewBox="0 0 48 48" {...props}>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.5 0 10.5-2.1 14.3-5.6l-6.6-5.6C29.6 34.6 26.9 35.5 24 35.5c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.6 39.6 16.3 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.3-4.1 5.7l6.6 5.6C41.7 36.1 44 30.5 44 24c0-1.3-.1-2.7-.4-3.5z" />
    </svg>
  );
}
