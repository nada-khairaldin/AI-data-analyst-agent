import React, { useState, useEffect } from 'react';

// "Once per page load" has to live outside the component: every mount gets
// fresh state, and the welcome screen is mounted again every time you come
// back to it.
let introPlayedAt = 0;

/**
 * The mark: three bars of a chart with a highlighter stroke across them.
 *
 * The dark bars are `currentColor`, not the #1D2321 of the source SVG. That
 * colour is near-black, and the sidebar it sits on is #08101D — the bars
 * would have vanished and left a lone yellow rectangle. Inheriting the text
 * colour makes it dark on the light screens and light on the dark sidebar
 * from one file. The yellow is fixed: it is the mark.
 *
 * `variant`:
 *   static   — no animation (the default, used everywhere but the two below)
 *   intro    — plays once per page load, ~800ms, then sits still
 *   loading  — the bars breathe in sequence until it unmounts
 *
 * The animations are CSS on the rects themselves; see index.css. Nothing
 * here blocks anything: the page is interactive while the intro plays.
 */
export default function Logo({ size = 32, className = '', title, variant = 'static' }) {
  const [playIntro, setPlayIntro] = useState(false);

  useEffect(() => {
    if (variant !== 'intro') return;
    const now = Date.now();
    // StrictMode unmounts and remounts immediately in development. Treating a
    // remount within two seconds as part of the same first paint keeps the
    // intro visible there instead of only in a production build.
    if (introPlayedAt && now - introPlayedAt > 2000) return;
    if (!introPlayedAt) introPlayedAt = now;
    setPlayIntro(true);
  }, [variant]);

  const mode =
    variant === 'loading' ? 'logo--loading' : playIntro ? 'logo--intro' : '';

  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      className={`${mode} ${className}`.trim()}
      role={title ? 'img' : 'presentation'}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {/* The rotation stays an attribute on a wrapper so the CSS transform on
          the rect itself is free to do the wipe; one element cannot carry
          both, the CSS one wins and the tilt would be lost. */}
      <g transform="rotate(-6 34 24.5)">
        <rect className="logo-wipe" x="26" y="6" width="16" height="37" rx="3" fill="#F2D45C" />
      </g>
      <rect className="logo-bar logo-bar--1" x="4" y="20" width="8" height="20" rx="2.5" fill="currentColor" />
      <rect className="logo-bar logo-bar--2" x="16" y="28" width="8" height="12" rx="2.5" fill="currentColor" />
      <rect className="logo-bar logo-bar--3" x="30" y="9" width="8" height="31" rx="2.5" fill="currentColor" />
    </svg>
  );
}
