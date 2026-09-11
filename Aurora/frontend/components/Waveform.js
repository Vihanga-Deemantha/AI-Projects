"use client";

import { useEffect, useRef } from "react";

/**
 * Canvas waveform visualizer. Reused for both mic input (while recording)
 * and TTS playback (while AURA is speaking) — whichever AnalyserNode is
 * passed in front, the drawing logic is identical.
 *
 * When `analyser` is null, renders a gentle bell-curve breathing animation
 * instead of a flat line, so the hero never looks "broken" between turns.
 *
 * `colorTop`/`colorBottom` paint each bar as a vertical gradient (matching
 * the AURA design system's soundwave) rather than a flat fill.
 */
export default function Waveform({
  analyser,
  colorTop = "#c3b8ff",
  colorBottom = "#7a68e8",
  barCount = 48,
}) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const idleTRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx2d = canvas.getContext("2d");

    const dataArray = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;

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

      const barWidth = width / barCount;
      const mid = height / 2;
      const barFillWidth = Math.max(1, barWidth * 0.6);

      const gradient = ctx2d.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, colorTop);
      gradient.addColorStop(1, colorBottom);
      ctx2d.fillStyle = gradient;

      if (analyser && dataArray) {
        analyser.getByteFrequencyData(dataArray);
      }

      for (let i = 0; i < barCount; i++) {
        let amplitude;
        if (analyser && dataArray) {
          const bin = dataArray[Math.floor((i / barCount) * dataArray.length)] || 0;
          amplitude = (bin / 255) * mid * 0.95;
        } else {
          // Idle: a bell-curve envelope (tall in the middle, short at the
          // edges) that breathes in and out together, matching the design's
          // resting soundwave rather than a wave traveling across the bars.
          const distFromCenter = Math.abs(i - barCount / 2) / (barCount / 2);
          const bellPeak = 1 - Math.pow(distFromCenter, 1.4);
          const pulse = Math.sin(idleTRef.current * 0.04) * 0.5 + 0.5;
          amplitude = (0.14 + bellPeak * 0.22 * pulse) * mid;
        }
        const barHeight = Math.max(2, amplitude);
        const x = i * barWidth + (barWidth - barFillWidth) / 2;
        ctx2d.globalAlpha = analyser ? 0.95 : 0.45;
        const radius = Math.min(barFillWidth / 2, 3);
        ctx2d.beginPath();
        if (ctx2d.roundRect) {
          ctx2d.roundRect(x, mid - barHeight, barFillWidth, barHeight * 2, radius);
        } else {
          ctx2d.rect(x, mid - barHeight, barFillWidth, barHeight * 2);
        }
        ctx2d.fill();
      }

      idleTRef.current += 1;
      rafRef.current = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      window.removeEventListener("resize", resize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [analyser, colorTop, colorBottom, barCount]);

  return <canvas ref={canvasRef} className="h-full w-full" />;
}
