"use client";

import { createContext, useContext, useRef, useState } from "react";
import { CAST, spriteSrc } from "@/lib/characters";
import Sprite from "@/components/Sprite";
import ThemeToggle from "@/components/ThemeToggle";

const AuthShellContext = createContext({ setLookAway: () => {} });

/** Lets the form beside the companion make them politely look away while a password is being typed. */
export function useAuthShell() {
  return useContext(AuthShellContext);
}

/**
 * The split card shared by /login, /signup and /forgot-password: a companion
 * panel on the left, the form (children) on the right. Moving the pointer over
 * the card tilts it and shifts each layer by a different amount so it reads as
 * dimensional. The companion's travel is capped to the panel's side padding so
 * they never clip.
 */
export default function AuthShell({ children }) {
  const [who, setWho] = useState(0);
  const [lookAway, setLookAway] = useState(false);
  const [tilt, setTilt] = useState({ px: 0, py: 0, inside: false });
  const raf = useRef(0);

  const c = CAST[who];

  function onMove(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * 2 - 1;
    const y = ((e.clientY - r.top) / r.height) * 2 - 1;
    if (raf.current) return;
    raf.current = requestAnimationFrame(() => {
      raf.current = 0;
      setTilt({ px: Math.max(-1, Math.min(1, x)), py: Math.max(-1, Math.min(1, y)), inside: true });
    });
  }

  function onLeave() {
    setTilt({ px: 0, py: 0, inside: false });
  }

  const { px, py, inside } = tilt;
  const d = (mult) => (inside ? px * mult : 0);
  const dy = (mult) => (inside ? py * mult : 0);
  const CLEAR = 24;
  const dChar = Math.max(-CLEAR, Math.min(CLEAR, d(26)));
  const ease = (fast, slow) => (inside ? fast : slow);

  return (
    <AuthShellContext.Provider value={{ setLookAway }}>
      <div className="relative grid min-h-screen flex-1 place-items-center overflow-hidden bg-background px-4 py-8 sm:px-6 sm:py-10">
        <div
          className="pointer-events-none absolute top-[-16%] right-[-10%] z-0 aspect-square w-[min(620px,60vw)] rounded-full bg-brand-soft"
          style={{ transform: `translate(${d(-30).toFixed(1)}px,${dy(-18).toFixed(1)}px)`, transition: `transform ${ease(".4s linear", "1s cubic-bezier(.22,1,.36,1)")}` }}
        />
        <div
          className="pointer-events-none absolute bottom-[-22%] left-[-12%] z-0 aspect-square w-[min(520px,52vw)] rounded-full bg-brand-soft opacity-70"
          style={{ transform: `translate(${d(22).toFixed(1)}px,${dy(14).toFixed(1)}px)`, transition: `transform ${ease(".4s linear", "1s cubic-bezier(.22,1,.36,1)")}` }}
        />

        <div
          className="aura-card-in relative z-2 w-full max-w-265 [perspective:1400px]"
          onMouseMove={onMove}
          onMouseLeave={onLeave}
        >
          <div
            className="relative overflow-hidden border border-panel-border bg-panel shadow-[var(--card-shadow)]"
            style={{
              transform: `rotateY(${d(3.4).toFixed(2)}deg) rotateX(${(-dy(2.4)).toFixed(2)}deg)`,
              transformStyle: "preserve-3d",
              transition: `transform ${ease(".18s linear", ".7s cubic-bezier(.22,1,.36,1)")}`,
            }}
          >
            <div className="grid md:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
              {/* Companion panel */}
              <section className="relative grid min-h-75 grid-cols-1 place-items-end justify-items-end overflow-hidden bg-brand-soft px-7.5 md:min-h-130 md:justify-items-center">
                <div
                  className="absolute top-[6%] left-1/2 aspect-square w-[78%] rounded-full bg-panel opacity-55"
                  style={{ transform: `translate(-50%,0) translate(${d(-16).toFixed(1)}px,${dy(-10).toFixed(1)}px)`, transition: `transform ${ease(".3s linear", ".8s cubic-bezier(.22,1,.36,1)")}` }}
                />
                <div
                  className="absolute inset-x-0 bottom-0 h-[18%] bg-brand opacity-[0.16]"
                  style={{ transform: `translate(${d(-6).toFixed(1)}px,0)`, transition: `transform ${ease(".3s linear", ".8s cubic-bezier(.22,1,.36,1)")}` }}
                />

                <div
                  className="relative z-3 -mb-0.5 h-52.5 max-w-full origin-bottom md:h-85"
                  style={{
                    aspectRatio: "700 / 680",
                    transform: `translate(${dChar.toFixed(1)}px,${dy(9).toFixed(1)}px) rotate(${d(1.6).toFixed(2)}deg)`,
                    transition: `transform ${ease(".22s linear", ".8s cubic-bezier(.34,1.32,.64,1)")}`,
                  }}
                >
                  <div className="absolute bottom-[-1%] left-[10%] h-4 w-[80%] rounded-full bg-foreground opacity-[0.16] blur-[9px]" />
                  <Sprite
                    key={c.id}
                    src={spriteSrc(c.id, "idle")}
                    alt={`${c.name}, AURA speaking companion`}
                    className="aura-char-in relative block h-full w-full transition-[filter] duration-500"
                    style={{ filter: lookAway ? "blur(7px)" : "none" }}
                  />
                </div>

                <div
                  className="pointer-events-none absolute inset-0 z-5 grid place-items-center bg-brand-soft transition-opacity duration-500"
                  style={{ opacity: lookAway ? 0.82 : 0 }}
                >
                  <span className="inline-flex items-center gap-2.25 bg-panel px-4 py-2.25 text-[10px] font-bold tracking-[0.2em] text-soft uppercase">
                    <span className="h-1.75 w-1.75 bg-brand" />
                    Not looking
                  </span>
                </div>

                <div className="absolute bottom-0 left-0 z-4 max-w-[52%] px-7.5 py-7">
                  <h2 className="font-display text-[clamp(28px,3.6vw,42px)] leading-[0.98] font-bold tracking-[-0.01em]">
                    Speak.<br />Listen.<br /><em className="font-medium">Improve.</em>
                  </h2>
                  <p className="mt-3 text-[12.5px] leading-normal text-soft">{c.line}</p>
                </div>

                <div className="absolute top-5.5 right-5.5 left-5.5 z-4 flex flex-wrap gap-1.5">
                  {CAST.map((x, i) => (
                    <button
                      key={x.id}
                      type="button"
                      title={x.name}
                      aria-label={`Show ${x.name}`}
                      onClick={() => setWho(i)}
                      className={`h-2.25 cursor-pointer transition-[width,background,opacity] duration-300 ${
                        i === who ? "w-5.5 bg-brand opacity-100" : "w-2.25 bg-panel opacity-75"
                      }`}
                    />
                  ))}
                </div>
              </section>

              {/* Form panel */}
              <section className="relative flex flex-col justify-center bg-panel px-6 py-14 sm:px-14 sm:py-13">
                <ThemeToggle className="absolute top-4.5 right-4.5 !h-7.5 !px-3.25 !text-[9.5px]" />
                <div className="flex items-center justify-center gap-2.5">
                  <span className="grid h-7.5 w-7.5 place-items-center bg-brand font-display text-[15px] font-bold text-on-brand">A</span>
                  <span className="font-display text-[19px] font-bold tracking-[0.18em]">AURA</span>
                </div>
                {children}
              </section>
            </div>
          </div>
        </div>
      </div>
    </AuthShellContext.Provider>
  );
}
