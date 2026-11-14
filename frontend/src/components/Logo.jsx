import React from 'react';

/**
 * The mark: three bars of a chart with a highlighter stroke across them.
 *
 * The dark bars are `currentColor`, not the #1D2321 of the source SVG. That
 * colour is near-black, and the sidebar it sits on is #08101D — the bars
 * would have vanished and left a lone yellow rectangle. Inheriting the text
 * colour makes it dark on the light screens and light on the dark sidebar
 * from one file. The yellow is fixed: it is the mark.
 */
export default function Logo({ size = 32, className = '', title }) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      className={className}
      role={title ? 'img' : 'presentation'}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <rect
        x="26"
        y="6"
        width="16"
        height="37"
        rx="3"
        fill="#F2D45C"
        transform="rotate(-6 34 24.5)"
      />
      <rect x="4" y="20" width="8" height="20" rx="2.5" fill="currentColor" />
      <rect x="16" y="28" width="8" height="12" rx="2.5" fill="currentColor" />
      <rect x="30" y="9" width="8" height="31" rx="2.5" fill="currentColor" />
    </svg>
  );
}
