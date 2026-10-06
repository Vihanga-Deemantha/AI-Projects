"use client";

import { useEffect, useRef } from "react";
import { usePrefersReducedMotion } from "@/hooks/motion";

/**
 * Canvas waveform visualizer. Reused for both mic input (while recording)
 * and TTS playback (while the companion is speaking) — whichever AnalyserNode
 * is passed in, the drawing logic is identical.
 *
 * When `analyser` is null, renders a low bell-curve "breathing" resting shape
 * instead of a flat line, so the stage never looks broken between turns. That
 * resting animation is decoration, so it is drawn at half rate (it costs a
 * laptop's battery for nothing) and, for someone who has asked their system
 * for reduced motion, not animated at all. A live microphone or voice level
 * is information rather than decoration, so it keeps moving.
 *
 * Bars are painted in the canvas's own CSS `color`, so a Tailwind text-color
 * class (e.g. `text-foreground`, `text-brand`) themes it — and it follows a
 * light/dark switch because the color is re-read while drawing.
 */
export default function Waveform({ analyser, barCount = 32, className = "text-foreground" }) {
  const canvasRef = useRef(null);
  const calm = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx2d = canvas.getContext("2d");

    const dataArray = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
    const still = !analyser && calm; // a resting shape for someone who asked for reduced motion: drawn, never animated
    let color = getComputedStyle(canvas).color;
    let frame = 0;
    let tick = 0;
    let handle = 0;
    // The canvas's size is read when it changes, not on every frame (asking for it forces the page to lay out again).
    let width = 0;
    let height = 0;

    function draw() {
      ctx2d.clearRect(0, 0, width, height);

      // Cheap enough to re-read twice a second, and keeps theme switches live.
      if (frame++ % 30 === 0) color = getComputedStyle(canvas).color;
      ctx2d.fillStyle = color;

      const barWidth = width / barCount;
      const barFillWidth = Math.max(2, barWidth * 0.55);
      const base = height;

      if (analyser && dataArray) {
        analyser.getByteFrequencyData(dataArray);
      }

      for (let i = 0; i < barCount; i++) {
        let amplitude;
        if (analyser && dataArray) {
          const bin = dataArray[Math.floor((i / barCount) * dataArray.length)] || 0;
          amplitude = (bin / 255) * height * 0.95;
        } else {
          // Idle: a bell-curve envelope (tall in the middle, short at the
          // edges) that breathes in and out together.
          const distFromCenter = Math.abs(i - barCount / 2) / (barCount / 2);
          const bellPeak = 1 - Math.pow(distFromCenter, 1.4);
          const pulse = still ? 0.5 : Math.sin(frame * 0.08) * 0.5 + 0.5;
          amplitude = (0.1 + bellPeak * 0.22 * pulse) * height;
        }
        const barHeight = Math.max(2, amplitude);
        const x = i * barWidth + (barWidth - barFillWidth) / 2;
        ctx2d.globalAlpha = analyser ? 0.9 : 0.3;
        ctx2d.fillRect(x, base - barHeight, barFillWidth, barHeight);
      }
    }

    function resize() {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (still) draw(); // resizing wipes the canvas, and a still waveform has no next frame to repaint it
    }

    function loop() {
      tick += 1;
      if (analyser || tick % 2 === 0) draw();
      handle = requestAnimationFrame(loop);
    }

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    if (still) {
      draw();
      handle = window.setInterval(draw, 500); // nothing moves; this only picks up a light/dark switch
    } else {
      loop();
    }

    return () => {
      observer.disconnect();
      if (still) window.clearInterval(handle);
      else cancelAnimationFrame(handle);
    };
  }, [analyser, barCount, calm]);

  // Purely decorative: the status text beside it says what is happening.
  return <canvas ref={canvasRef} aria-hidden="true" className={`h-full w-full ${className}`} />;
}
