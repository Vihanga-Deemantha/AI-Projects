import { Bodoni_Moda, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

const bodoniModa = Bodoni_Moda({
  variable: "--font-bodoni",
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: ["400", "500", "600", "700", "800", "900"],
});

const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata = {
  title: "AURA — AI English Speaking Coach",
  description: "Practice real-time spoken English with an AI coach that gives grammar and vocabulary feedback.",
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${bodoniModa.variable} ${plusJakartaSans.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* Sets data-theme from localStorage before first paint — must run
            synchronously, before React hydrates, or a saved Clarity (light)
            choice would flash as Midnight (the CSS default) on every load. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <div className="aura-glow-bg" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
