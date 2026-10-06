"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import AppSidebar from "@/components/AppSidebar";
import DifficultyLabel from "@/components/DifficultyLabel";
import { getDifficulty, getOptions } from "@/lib/api";
import {
  changePassword,
  deleteAccount,
  disconnectGoogle,
  getGoogleAuthUrl,
  getMe,
  startGoogleAuth,
  updateProfile,
  uploadAvatar,
} from "@/lib/auth";
import { speaks, styleAccent, whyNot, withArticle } from "@/lib/accents";
import { CAST, companionHint, faceSrc } from "@/lib/characters";

const GOOGLE_LINK_ERRORS = {
  google_not_configured: "Google sign-in isn't set up on this server yet.",
  google_link_mismatch: "That Google account's email doesn't match your AURA account. Sign out of Google and try again with the matching account.",
  google_link_conflict: "That Google account is already linked to a different AURA account.",
  google_failed: "Connecting Google didn't complete. Please try again.",
};

const input =
  "h-12 w-full border border-transparent bg-field px-3.75 text-[14.5px] text-foreground outline-none transition focus:border-brand";
const label = "mb-1.75 block text-[10px] font-bold tracking-[0.16em] text-soft uppercase";
const primaryBtn =
  "h-11.5 cursor-pointer bg-foreground px-6 text-[10px] font-bold tracking-[0.18em] whitespace-nowrap text-background uppercase transition hover:bg-brand hover:text-on-brand disabled:cursor-not-allowed disabled:opacity-50";
const secondaryBtn =
  "h-10 cursor-pointer border border-panel-border px-4.5 text-[10px] font-bold tracking-[0.16em] whitespace-nowrap text-soft uppercase transition hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-40";

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

  // "Change" next to the difficulty on the practice page links to #difficulty; that card
  // only exists once the profile has loaded, so the browser's own anchor jump can't find it.
  useEffect(() => {
    if (status === "ready" && window.location.hash === "#difficulty") {
      document.getElementById("difficulty")?.scrollIntoView();
    }
  }, [status]);

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
    <main className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10 lg:pt-9 lg:pb-14">
      <div className="max-w-190">
        <header>
          <div className="text-[10px] font-bold tracking-[0.22em] text-soft uppercase">Account</div>
          <h1 className="mt-2.5 font-display text-[clamp(30px,3.6vw,46px)] leading-none font-bold">Your profile</h1>
        </header>

        {status === "loading" && <p className="mt-6.5 text-sm text-mute">Loading…</p>}
        {status === "error" && (
          <div role="alert" className="mt-6.5 border border-brand bg-brand-soft px-4 py-3 text-sm">
            Couldn&apos;t load your profile. Try refreshing the page.
          </div>
        )}

        {status === "ready" && (
          <>
            <IdentityCard user={user} onUpdated={setUser} />
            <PersonalInfoCard user={user} onUpdated={setUser} />
            <CompanionsCard user={user} onUpdated={setUser} />
            <DifficultyCard user={user} onUpdated={setUser} />
            <SecurityCard user={user} onUpdated={setUser} />
            <ConnectedAccountsCard user={user} onUpdated={setUser} linkError={linkError} />
            <DangerZoneCard user={user} />
          </>
        )}
      </div>
    </main>
  );
}

function Card({ id, title, subtitle, children }) {
  return (
    <section id={id} className="mt-5.5 scroll-mt-6 border border-panel-border bg-panel p-6.5">
      <h2 className="font-display text-xl font-bold">{title}</h2>
      {subtitle && <p className="mt-2 text-[13.5px] text-soft">{subtitle}</p>}
      {children}
    </section>
  );
}

function Notice({ children }) {
  return <p className="mt-3 border-l-2 border-brand bg-brand-soft px-3 py-2 text-xs">{children}</p>;
}

function IdentityCard({ user, onUpdated }) {
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
    <section className="mt-6.5 border border-panel-border bg-panel p-6.5">
      <div className="flex flex-wrap items-center gap-5.5">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          aria-label="Change photo"
          className="group relative h-21 w-21 shrink-0 cursor-pointer overflow-hidden rounded-full disabled:cursor-wait"
        >
          {user.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- avatar comes from an external Cloudinary/Google CDN, not a locally-optimizable asset
            <img src={user.avatar_url} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="grid h-full w-full place-items-center bg-brand font-display text-[32px] font-bold text-on-brand">
              {initial}
            </span>
          )}
          <span className="absolute inset-0 grid place-items-center bg-black/50 text-[10px] font-bold tracking-widest text-white uppercase opacity-0 transition group-hover:opacity-100">
            {uploading ? "Uploading…" : "Change"}
          </span>
        </button>
        <div className="min-w-0 flex-[1_1_220px]">
          <div className="truncate font-display text-2xl font-bold">{user.display_name || "Your name"}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px] text-mute">
            <span className="truncate">{user.email}</span>
            {user.email_verified ? (
              <span className="text-[10px] font-bold tracking-[0.14em] text-brand uppercase">Verified</span>
            ) : (
              <Link
                href="/verify-email"
                className="text-[10px] font-bold tracking-[0.14em] text-foreground uppercase underline underline-offset-[3px] transition hover:text-brand"
              >
                Not verified — verify now
              </Link>
            )}
          </div>
          <p className="mt-2 text-xs text-mute">JPEG, PNG or WebP — up to 5 MB.</p>
        </div>
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading} className={secondaryBtn}>
          {uploading ? "Uploading…" : "Change photo"}
        </button>
        <input
          ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp"
          className="hidden" onChange={handleFileChange}
        />
      </div>
      {error && <Notice>{error}</Notice>}
    </section>
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
    <Card title="Personal info">
      <label className="mt-4.5 block">
        <span className={label}>Display name</span>
        <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={100} className={input} />
      </label>
      <label className="mt-4 block">
        <span className="mb-1.75 flex items-center justify-between">
          <span className="text-[10px] font-bold tracking-[0.16em] text-soft uppercase">Bio</span>
          <span className="text-[10px] text-mute">{bio.length}/300</span>
        </span>
        <textarea
          value={bio} onChange={(e) => setBio(e.target.value.slice(0, 300))} rows={3}
          placeholder="Tell us a bit about your English learning goals."
          className="w-full resize-none border border-transparent bg-field px-3.75 py-3.25 text-[14.5px] leading-[1.55] text-foreground outline-none transition focus:border-brand"
        />
      </label>
      {error && <Notice>{error}</Notice>}
      <div className="mt-4.5 flex items-center gap-3">
        <button type="button" onClick={handleSave} disabled={saving} className={primaryBtn}>
          {saving ? "Saving…" : "Save changes"}
        </button>
        {saved && <span className="text-sm font-semibold text-brand">Saved</span>}
      </div>
    </Card>
  );
}

function CompanionsCard({ user, onUpdated }) {
  const [options, setOptions] = useState(null);
  const styles = options?.styles ?? [];
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getOptions().then(setOptions).catch(() => {});
  }, []);

  // A pair saved before styles brought an accent (or from a voice that has since gone) may have no voice behind it.
  const savedAccent = styleAccent(options, user.preferred_style);
  const savedPairBroken = Boolean(options) && !speaks(options, user.preferred_voice, user.preferred_style);
  const savedName = CAST.find((c) => c.id === user.preferred_voice)?.name ?? "Your companion";

  async function save(patch) {
    setSaving(true);
    setError(null);
    try {
      onUpdated(await updateProfile(patch));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Your companions" subtitle="Pick who greets you when you open a session, and the English you'd like to hear.">
      <div className="mt-4.5 flex flex-wrap gap-3">
        {CAST.map((c) => {
          const active = c.id === user.preferred_voice;
          const can = speaks(options, c.id, user.preferred_style);
          const accentNow = styleAccent(options, user.preferred_style);
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => save({ preferredVoice: c.id })}
              disabled={saving || !can}
              aria-pressed={active}
              title={can ? companionHint(c, accentNow) : whyNot(options, c.id, user.preferred_style)}
              className={`flex w-26 flex-col items-center gap-1.75 border px-2.5 py-4 transition ${
                saving ? "cursor-wait" : can ? "cursor-pointer" : "cursor-not-allowed"
              } ${can ? "" : "opacity-40"} ${active ? "border-brand bg-brand-soft" : "border-panel-border hover:border-brand"}`}
            >
              <span
                role="img"
                aria-label={c.name}
                className="h-13.5 w-13.5 rounded-full bg-brand-soft bg-cover bg-top"
                style={{ backgroundImage: `url('${faceSrc(c.id, "smiling")}')` }}
              />
              <span className="font-display text-[15px] font-bold">{c.name}</span>
              <span className="text-[9px] font-bold tracking-[0.14em] text-mute uppercase">{c.tag}</span>
            </button>
          );
        })}
      </div>

      {styles.length > 0 && (
        <div className="mt-5.5">
          <div className={label}>Speaking style</div>
          <div className="flex flex-wrap">
            {styles.map((s) => {
              const active = s.id === user.preferred_style;
              const can = speaks(options, user.preferred_voice, s.id);
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => save({ preferredStyle: s.id })}
                  disabled={saving || !can}
                  aria-pressed={active}
                  title={can ? undefined : whyNot(options, user.preferred_voice, s.id)}
                  className={`-mr-px -mb-px border px-3.5 py-2.25 text-[12.5px] whitespace-nowrap transition ${
                    saving ? "cursor-wait" : can ? "cursor-pointer" : "cursor-not-allowed"
                  } ${can ? "" : "opacity-40"} ${active ? "border-brand bg-brand font-bold text-on-brand" : "border-panel-border font-medium text-soft hover:border-brand"}`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
          <p className="mt-2.5 text-[11.5px] leading-normal text-mute">
            A style sets the words your coach uses and the accent you hear: your companion adopts it. Dimmed styles have no matching voice for
            this companion yet.
          </p>
          <p className="mt-2 text-[11px] leading-normal text-mute">
            Regional accents use real speakers from the CSTR VCTK Corpus and the Alba voice (University of Edinburgh, CC BY 4.0), run with Piper.
          </p>
        </div>
      )}
      {savedPairBroken && (
        <Notice>
          {savedAccent
            ? `${savedName} doesn't have ${withArticle(savedAccent)} voice yet, so your sessions will start in Standard English until you pick a different companion or style.`
            : "Your saved speaking style isn't available on this server, so your sessions will start in Standard English until you pick another."}
        </Notice>
      )}
      {error && <Notice>{error}</Notice>}
    </Card>
  );
}

/**
 * Pin a difficulty level, or leave it automatic (the level follows how recent sessions
 * scored). `user.difficulty_override` is the pinned level, or null for automatic.
 */
function DifficultyCard({ user, onUpdated }) {
  const [levels, setLevels] = useState([]);
  const [info, setInfo] = useState(null); // GET /api/practice/difficulty
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getOptions().then((o) => setLevels(o.difficulties)).catch(() => {});
    getDifficulty().then(setInfo).catch(() => {});
  }, []);

  async function choose(difficultyOverride) {
    setSaving(true);
    setError(null);
    try {
      onUpdated(await updateProfile({ difficultyOverride }));
      setInfo(await getDifficulty());
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const pinned = user.difficulty_override ?? null;
  const chip = (active) =>
    `-mr-px -mb-px cursor-pointer border px-3.5 py-2.25 text-[12.5px] whitespace-nowrap transition disabled:cursor-wait ${
      active ? "border-brand bg-brand font-bold text-on-brand" : "border-panel-border font-medium text-soft hover:border-brand"
    }`;

  return (
    <Card
      id="difficulty"
      title="Difficulty"
      subtitle="How demanding your coach's questions are. Automatic follows how your recent sessions went, one step at a time."
    >
      <div className="mt-4.5 flex flex-wrap" role="group" aria-label="Difficulty level">
        <button type="button" onClick={() => choose(null)} disabled={saving} aria-pressed={pinned === null} className={chip(pinned === null)}>
          Automatic
        </button>
        {levels.map((l) => (
          <button
            key={l.level}
            type="button"
            onClick={() => choose(l.level)}
            disabled={saving}
            aria-pressed={pinned === l.level}
            className={chip(pinned === l.level)}
          >
            {l.label}
          </button>
        ))}
      </div>

      {info && (
        <div className="mt-4.5">
          <div className="text-[10px] font-bold tracking-[0.16em] text-soft uppercase">{info.mode === "manual" ? "Your level" : "Right now"}</div>
          <div className="mt-1.5 font-display text-[19px] leading-none font-bold">
            <DifficultyLabel level={info} />
          </div>
          <p className="mt-2 text-[13px] leading-normal text-soft">
            {info.reason}
            {info.mode === "manual" && ` Automatic would currently choose ${info.auto_label}.`}
          </p>
          <p className="mt-1 text-[13px] leading-normal text-mute">For example: &ldquo;{info.example}&rdquo;</p>
        </div>
      )}
      {error && <Notice>{error}</Notice>}
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
      // Other sessions are signed out by the server; this one gets a fresh token.
      const updated = await changePassword({ currentPassword: user.has_password ? current : undefined, newPassword: next });
      onUpdated(updated);
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
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold">Password</div>
          <div className="mt-0.75 text-[12.5px] text-mute">
            {user.has_password ? "Sign in with your email and password." : "Not set — you currently sign in with Google only."}
          </div>
        </div>
        <button type="button" onClick={() => setExpanded((v) => !v)} className={secondaryBtn}>
          {expanded ? "Cancel" : user.has_password ? "Change password" : "Set a password"}
        </button>
      </div>

      {expanded && (
        <form onSubmit={handleSubmit} className="mt-4.5 flex flex-col gap-3">
          {user.has_password && (
            <input
              type="password" required value={current} onChange={(e) => setCurrent(e.target.value)}
              placeholder="Current password" autoComplete="current-password" className={input}
            />
          )}
          <input
            type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)}
            placeholder="New password" autoComplete="new-password" className={input}
          />
          <input
            type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
            placeholder="Confirm new password" autoComplete="new-password" className={input}
          />
          {error && <Notice>{error}</Notice>}
          <div className="flex items-center gap-3">
            <button type="submit" disabled={saving} className={primaryBtn}>
              {saving ? "Saving…" : user.has_password ? "Update password" : "Set password"}
            </button>
            {saved && <span className="text-sm font-semibold text-brand">Updated</span>}
          </div>
        </form>
      )}
      {!expanded && saved && <p className="mt-3 text-sm font-semibold text-brand">Password updated</p>}
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
    <Card title="Connected accounts">
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <GoogleIcon className="h-5 w-5" />
          <div>
            <div className="text-sm font-semibold">Google</div>
            <div className="mt-0.75 text-[12.5px] text-mute">{user.google_linked ? "Connected" : "Not connected"}</div>
          </div>
        </div>

        {user.google_linked ? (
          <button
            type="button"
            onClick={handleDisconnect}
            disabled={!canDisconnect || disconnecting}
            title={canDisconnect ? undefined : "Set a password before disconnecting Google"}
            className={secondaryBtn}
          >
            {disconnecting ? "Disconnecting…" : "Disconnect"}
          </button>
        ) : (
          <a
            href={getGoogleAuthUrl()}
            onClick={(e) => startGoogleAuth(e, { link: true, onError: setError })}
            className={`${secondaryBtn} inline-flex items-center`}
          >
            Connect
          </a>
        )}
      </div>
      {(error || linkError) && <Notice>{error || linkError}</Notice>}
    </Card>
  );
}

function DangerZoneCard({ user }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  async function handleDelete(e) {
    e.preventDefault();
    setError(null);
    setDeleting(true);
    try {
      await deleteAccount({ confirmEmail, password: user.has_password ? password : undefined });
      router.replace("/");
    } catch (err) {
      setError(err.message);
      setDeleting(false);
    }
  }

  return (
    <Card title="Delete account">
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-[34em] text-[13px] leading-normal text-soft">
          Permanently removes your account and everything under it — every session, transcript,
          correction and report. This can&apos;t be undone.
        </p>
        <button type="button" onClick={() => setExpanded((v) => !v)} className={secondaryBtn}>
          {expanded ? "Cancel" : "Delete my account"}
        </button>
      </div>

      {expanded && (
        <form onSubmit={handleDelete} className="mt-4.5 flex flex-col gap-3">
          <input
            type="email" required value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)}
            placeholder={`Type ${user.email} to confirm`} autoComplete="off" className={input}
          />
          {user.has_password && (
            <input
              type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password" autoComplete="current-password" className={input}
            />
          )}
          {error && <Notice>{error}</Notice>}
          <div>
            <button
              type="submit"
              disabled={deleting || confirmEmail.trim().toLowerCase() !== (user.email || "").toLowerCase()}
              className={primaryBtn}
            >
              {deleting ? "Deleting…" : "Permanently delete"}
            </button>
          </div>
        </form>
      )}
    </Card>
  );
}

function GoogleIcon(props) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" {...props}>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.8-6.8C35.6 2.3 30.2 0 24 0 14.6 0 6.5 5.4 2.5 13.3l7.9 6.1C12.3 13.5 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-2.8-.4-4.1H24v8.4h12.5c-.3 2.1-1.6 5.2-4.6 7.3l7.7 6c4.6-4.2 6.5-10.3 6.5-17.6z" />
      <path fill="#FBBC05" d="M10.4 28.6c-.5-1.5-.8-3-.8-4.6s.3-3.1.8-4.6l-7.9-6.1C.9 16.5 0 20.1 0 24s.9 7.5 2.5 10.7l7.9-6.1z" />
      <path fill="#34A853" d="M24 48c6.2 0 11.5-2 15.3-5.6l-7.7-6c-2.1 1.4-4.8 2.3-7.6 2.3-6.3 0-11.7-4-13.6-9.9l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}
