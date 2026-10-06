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

export const metadata = {
  title: "AURA — AI English Speaking Coach",
  description: "Practise real spoken English with six AI companions that give you grammar and vocabulary feedback after every turn.",
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
