"use client";

import { useEffect, useRef, useState } from "react";

const LENGTH = 6;

/**
 * Six-box OTP entry. Auto-advances on digit entry, backspace navigates back,
 * paste distributes across boxes. Calls onChange(otpString) on every edit,
 * and onComplete(otpString) once all six boxes are filled.
 *
 * `error` triggers a brief shake + red border on the boxes without owning
 * their value — the parent clears it by changing key/remounting or just
 * lets the next edit implicitly move on.
 */
export default function OTPInput({ onComplete, error, disabled }) {
  const [digits, setDigits] = useState(Array(LENGTH).fill(""));
  const inputRefs = useRef([]);

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  function setDigitAt(index, value) {
    const next = [...digits];
    next[index] = value;
    setDigits(next);
    const otp = next.join("");
    if (otp.length === LENGTH && next.every((d) => d !== "")) {
      onComplete?.(otp);
    }
  }

  function handleChange(index, e) {
    const raw = e.target.value.replace(/\D/g, "");
    if (!raw) {
      setDigitAt(index, "");
      return;
    }
    // Typing a digit when one is already there (cursor at start) replaces it.
    const digit = raw.slice(-1);
    setDigitAt(index, digit);
    if (index < LENGTH - 1) inputRefs.current[index + 1]?.focus();
  }

  function handleKeyDown(index, e) {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
      setDigitAt(index - 1, "");
    }
  }

  function handlePaste(e) {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, LENGTH);
    if (!pasted) return;
    const next = Array(LENGTH).fill("");
    for (let i = 0; i < pasted.length; i++) next[i] = pasted[i];
    setDigits(next);
    const focusIndex = Math.min(pasted.length, LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();
    if (pasted.length === LENGTH) onComplete?.(pasted);
  }

  return (
    <div className={`flex justify-center gap-1 sm:gap-2.5 ${error ? "animate-shake" : ""}`}>
      {digits.map((digit, i) => (
        <input
          key={i}
          ref={(el) => {
            inputRefs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={digit}
          disabled={disabled}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          className={`h-9 w-9 rounded-[13px] border-2 bg-foreground/5 text-center font-display text-base font-bold outline-none transition focus:ring-4 focus:ring-brand/15 disabled:opacity-50 sm:h-12 sm:w-12 sm:text-xl ${
            error ? "border-rose-500" : "border-panel-border focus:border-brand"
          }`}
        />
      ))}
    </div>
  );
}
