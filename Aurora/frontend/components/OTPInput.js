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
    <div className={`flex justify-center gap-1 sm:gap-2.25 ${error ? "animate-shake" : ""}`}>
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
