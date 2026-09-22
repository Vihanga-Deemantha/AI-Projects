"use client";

/**
 * A user's own avatar: their uploaded photo if they have one, otherwise a
 * solid circle with their initial. Shared by the sidebar and the chat
 * bubbles so a user without a photo still reads as "them" everywhere.
 */
export default function UserAvatar({ user, className = "" }) {
  if (user?.avatar_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- external Cloudinary/Google CDN URL, not a locally-optimizable asset
      <img src={user.avatar_url} alt="" className={`rounded-full object-cover ${className}`} />
    );
  }
  const initial = (user?.display_name || user?.email || "A").charAt(0).toUpperCase();
  return (
    <span className={`grid place-items-center rounded-full bg-brand font-display font-bold text-on-brand ${className}`}>
      {initial}
    </span>
  );
}
