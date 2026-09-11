import Link from "next/link";

/**
 * The left-hand "brand" panel on the split-panel auth screens — an orb with
 * a couple of floating illustrative cards and a pull-quote, replacing a bare
 * centered form with something that actually shows what AURA does.
 *
 * `floatingCards` takes 0-2 small `{ lines: [...] }` cards positioned around
 * the orb; `quote`/`subtext` sit at the bottom.
 */
export default function AuthBrandPanel({ quote, subtext, floatingCards = [] }) {
  return (
    <div className="relative hidden w-[56%] flex-col justify-between overflow-hidden bg-linear-to-br from-brand-soft via-background to-background p-14 lg:flex">
      <div className="pointer-events-none absolute -top-40 -left-36 h-[560px] w-[560px] rounded-full bg-brand/15 blur-3xl" />

      <Link href="/" className="relative z-10 flex items-center gap-3">
        <span className="flex h-8.5 w-8.5 items-center justify-center rounded-[10px] bg-linear-to-br from-brand to-brand-dark font-display font-bold text-white shadow-[0_0_18px_rgba(139,124,255,0.5)]">
          A
        </span>
        <span className="font-display text-xl font-bold">AURA</span>
      </Link>

      <div className="relative z-[2] flex flex-1 items-center justify-center">
        <div className="relative flex h-70 w-70 items-center justify-center">
          <div className="aura-ring-spin absolute -inset-8 rounded-full bg-[conic-gradient(from_0deg,transparent,rgba(139,124,255,0.45),transparent_40%)]" />
          <div className="aura-orb-breathe h-46 w-46 rounded-full bg-[radial-gradient(circle_at_36%_30%,#b4a8ff_0%,#8b7cff_34%,#5541c9_70%,#2c1f6b_100%)] shadow-[0_0_70px_rgba(139,124,255,0.55)]" />

          {floatingCards[0] && (
            <div className="absolute top-1.5 -left-23 rounded-2xl border border-panel-border bg-panel/90 px-4 py-3 shadow-2xl backdrop-blur">
              {floatingCards[0].lines.map((line, i) => (
                <p key={i} className={i === 0 ? "text-[11px] font-bold text-emerald-500" : "mt-0.5 text-[10px] text-foreground/40"}>
                  {line}
                </p>
              ))}
            </div>
          )}
          {floatingCards[1] && (
            <div className="absolute -right-27 bottom-0.5 rounded-2xl border border-panel-border bg-panel/90 px-4 py-3 shadow-2xl backdrop-blur">
              {floatingCards[1].lines.map((line, i) => (
                <p key={i} className={i === 0 ? "text-[11px] font-bold text-brand" : "mt-0.5 text-[10px] text-foreground/40"}>
                  {line}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="relative z-10">
        <h2 className="max-w-md font-display text-[28px] leading-[1.3] font-bold italic">{quote}</h2>
        <p className="mt-3 text-[13.5px] text-foreground/45">{subtext}</p>
      </div>
    </div>
  );
}
