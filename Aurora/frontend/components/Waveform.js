"use client";

import { useEffect, useRef } from "react";

/**
 * Canvas waveform visualizer. Reused for both mic input (while recording)
 * and TTS playback (while AURA is speaking) — whichever AnalyserNode is
 * passed in front, the drawing logic is identical.
 *
 * When `analyser` is null, renders a gentle idle animation instead of a
 * flat line, so the hero never looks "broken" between turns.
 */
export default function Waveform({ analyser, color = "#6366f1", barCount = 48 }) {
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

      if (analyser && dataArray) {
        analyser.getByteFrequencyData(dataArray);
      }

      for (let i = 0; i < barCount; i++) {
        let amplitude;
        if (analyser && dataArray) {
          const bin = dataArray[Math.floor((i / barCount) * dataArray.length)] || 0;
          amplitude = (bin / 255) * mid * 0.95;
        } else {
          // Idle: slow, gentle sine sway so the hero stays alive between turns.
          const phase = idleTRef.current * 0.03 + i * 0.35;
          amplitude = (Math.sin(phase) * 0.5 + 0.5) * mid * 0.18;
        }
        const barHeight = Math.max(2, amplitude);
        const x = i * barWidth + barWidth * 0.2;
        ctx2d.fillStyle = color;
        ctx2d.globalAlpha = analyser ? 0.9 : 0.35;
        ctx2d.fillRect(x, mid - barHeight, barWidth * 0.6, barHeight * 2);
      }

      idleTRef.current += 1;
      rafRef.current = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      window.removeEventListener("resize", resize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [analyser, color, barCount]);

  return <canvas ref={canvasRef} className="h-full w-full" />;
}
