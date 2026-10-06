"use client";

import { useEffect, useRef, useState } from "react";

const LENGTH = 6;

/**
 * Six-box OTP entry. Auto-advances on digit entry, backspace navigates back,
 * paste distributes across boxes. Calls onComplete(otpString) once all six
 * boxes are filled.
 *
 * `error` triggers a brief shake + accent border on the boxes without owning
 * their value — the parent clears it by remounting (changing `key`).
 */
export default function OTPInput({ onComplete, error, disabled }) {
  const [digits, setDigits] = useState(Array(LENGTH).fill(""));
  const inputRefs = useRef([]);
  // The source of truth for the digits typed so far. State alone isn't enough:
  // several keystrokes (fast typing, autofill, a paste handler) can arrive
  // before React re-renders, and each would then build its update from the
  // same stale array and overwrite the others.
  const digitsRef = useRef(Array(LENGTH).fill(""));

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  function commit(next) {
    digitsRef.current = next;
    setDigits(next);
    if (next.every((d) => d !== "")) onComplete?.(next.join(""));
  }

  function setDigitAt(index, value) {
    const next = [...digitsRef.current];
    next[index] = value;
    commit(next);
  }

  /** Spreads several digits across the boxes starting at `from` (paste, SMS autofill). */
  function fillFrom(from, digitsToPlace) {
    const next = [...digitsRef.current];
    const placed = digitsToPlace.slice(0, LENGTH - from);
    for (let i = 0; i < placed.length; i++) next[from + i] = placed[i];
    inputRefs.current[Math.min(from + placed.length, LENGTH - 1)]?.focus();
    commit(next);
  }

  function handleChange(index, e) {
    const raw = e.target.value.replace(/\D/g, "");
    if (!raw) {
      setDigitAt(index, "");
      return;
    }
    // More than two digits arriving at once is a pasted/auto-filled code (a
    // phone's one-time-code suggestion lands in the first box in one go), not
    // someone typing over a box that already had a digit.
    if (raw.length > 2) {
      fillFrom(index, raw);
      return;
    }
    // Typing a digit when one is already there (cursor at start) replaces it.
    setDigitAt(index, raw.slice(-1));
    if (index < LENGTH - 1) inputRefs.current[index + 1]?.focus();
  }

  function handleKeyDown(index, e) {
    if (e.key === "Backspace" && !digitsRef.current[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
      setDigitAt(index - 1, "");
    }
  }

  function handlePaste(e) {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, LENGTH);
    if (!pasted) return;
    // A pasted code always replaces whatever was typed, starting from the first box.
    digitsRef.current = Array(LENGTH).fill("");
    fillFrom(0, pasted);
  }

  return (
    <div className={`flex justify-center gap-1 sm:gap-2.25 ${error ? "animate-shake" : ""}`}>
      {digits.map((digit, i) => (
        <input
          key={i}
          ref={(el) => {
            inputRefs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          // Room for the rest of the code from this box on, so an autofilled
          // code isn't truncated to one character by the browser.
          maxLength={LENGTH - i}
          value={digit}
          disabled={disabled}
          aria-label={`Digit ${i + 1}`}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          className={`h-11 w-9 border bg-field p-0 text-center font-display text-lg font-bold text-foreground outline-none transition focus:border-brand disabled:opacity-50 sm:h-13.5 sm:w-11.5 sm:text-[21px] ${
            error || digit ? "border-brand" : "border-transparent"
          }`}
        />
      ))}
    </div>
  );
}
