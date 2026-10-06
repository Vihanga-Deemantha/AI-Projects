/**
 * Response headers sent with every page.
 *
 * The Content-Security-Policy is deliberately the short subset that is safe on statically built pages:
 * it stops the app being framed by another site (clickjacking), stops injected <base>/<object> tags and
 * keeps forms posting to this site. A strict `script-src` would need a fresh nonce for every request,
 * which Next only supports on dynamically rendered pages, and that would give up prerendering the whole
 * app. The login token lives in localStorage (see the README's security notes), so keep scripts to
 * trusted code: no third-party script tags, and no dangerouslySetInnerHTML except the fixed theme snippet.
 */
const securityHeaders = [
  { key: "Content-Security-Policy", value: "base-uri 'self'; object-src 'none'; form-action 'self'; frame-ancestors 'none'" },
  { key: "X-Frame-Options", value: "DENY" }, // the same rule for browsers that predate frame-ancestors
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // The microphone is the only powerful feature AURA uses, and only on its own pages.
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=(), payment=(), usb=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
