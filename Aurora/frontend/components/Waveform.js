"use client";

import { useEffect, useRef } from "react";

/**
 * Canvas waveform visualizer. Reused for both mic input (while recording)
 * and TTS playback (while the companion is speaking) — whichever AnalyserNode
 * is passed in, the drawing logic is identical.
 *
 * When `analyser` is null, renders a low bell-curve "breathing" resting shape
 * instead of a flat line, so the stage never looks broken between turns.
 *
 * Bars are painted in the canvas's own CSS `color`, so a Tailwind text-color
 * class (e.g. `text-foreground`, `text-brand`) themes it — and it follows a
 * light/dark switch because the color is re-read while drawing.
 */
export default function Waveform({ analyser, barCount = 32, className = "text-foreground" }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const idleTRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx2d = canvas.getContext("2d");

    const dataArray = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
    let color = getComputedStyle(canvas).color;
    let frame = 0;

    function resize() {
      const { width, height } = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    function draw() {
      const { width, height } = canvas.getBoundingClientRect();
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
          const pulse = Math.sin(idleTRef.current * 0.04) * 0.5 + 0.5;
          amplitude = (0.1 + bellPeak * 0.22 * pulse) * height;
        }
        const barHeight = Math.max(2, amplitude);
        const x = i * barWidth + (barWidth - barFillWidth) / 2;
        ctx2d.globalAlpha = analyser ? 0.9 : 0.3;
        ctx2d.fillRect(x, base - barHeight, barFillWidth, barHeight);
      }

      idleTRef.current += 1;
      rafRef.current = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      window.removeEventListener("resize", resize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [analyser, barCount]);

  return <canvas ref={canvasRef} className={`h-full w-full ${className}`} />;
}
