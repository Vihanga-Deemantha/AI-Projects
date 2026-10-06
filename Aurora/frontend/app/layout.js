import { Playfair_Display, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
});

// Plus Jakarta Sans is a *variable* font, so next/font wants no `weight` at all
// (every weight 200–800 is already in the one file). Passing an array of
// weights — which is only valid for static fonts — makes `next build` fail under
// Turbopack with "next/font/google queries have exactly one entry".
const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  display: "swap",
});

const TITLE = "AURA — AI English Speaking Coach";
const DESCRIPTION = "Practise real spoken English with six AI companions that give you grammar and vocabulary feedback after every turn.";

export const metadata = {
  // The address link previews are built from (NEXT_PUBLIC_SITE_URL once the app has one).
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  // Each section sets a short title ("Practice"); the template turns it into "Practice — AURA".
  title: { default: TITLE, template: "%s — AURA" },
  description: DESCRIPTION,
  // The preview image comes from app/opengraph-image.js.
  openGraph: { title: TITLE, description: DESCRIPTION, siteName: "AURA", type: "website", locale: "en_US" },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

// Colours the browser's own chrome (the phone's address bar) to match the page.
export const viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0d" },
  ],
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${playfair.variable} ${plusJakartaSans.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* Sets data-theme from localStorage before first paint — must run
            synchronously, before React hydrates, or a saved choice would
            flash as the OS default on every load. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground">{children}</body>
    </html>
  );
}
