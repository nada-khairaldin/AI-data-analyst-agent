import React, { useState, useEffect } from 'react';

const CIRCUMFERENCE = 283; // r=45
const DURATION = 1000;

// Count the decimals the server used, so 92.9% does not animate to 92.90%
// and 100% does not land on 100.0%.
function decimalsOf(text) {
  const match = String(text ?? '').match(/\.(\d+)/);
  return match ? match[1].length : 0;
}

const easeOutCubic = (t) => 1 - (1 - t) ** 3;

/**
 * Fills from zero to `score` once per `animationKey`. Re-renders that do not
 * change the key leave the ring alone — otherwise every unrelated state
 * change in the parent would replay the animation.
 */
export default function QualityRing({ score, scoreText, label, colorClass, animationKey }) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    if (reduced || !Number.isFinite(score)) {
      setShown(score || 0);
      return undefined;
    }

    let frame;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min((now - start) / DURATION, 1);
      setShown(score * easeOutCubic(progress));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [score, animationKey]);

  const decimals = decimalsOf(scoreText);
  const offset = Math.max(0, CIRCUMFERENCE - (CIRCUMFERENCE * shown) / 100);

  return (
    <div className="relative w-32 h-32 mb-4">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="currentColor"
          className="text-slate-100 dark:text-dark-border"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="currentColor"
          className={colorClass}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-2xl font-bold text-slate-800 dark:text-white tabular-nums">
          {shown.toFixed(decimals)}%
        </span>
        <span className={`text-xs font-medium ${colorClass}`}>{label}</span>
      </div>
    </div>
  );
}
