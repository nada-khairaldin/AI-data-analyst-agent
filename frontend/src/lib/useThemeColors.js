import { useEffect, useState } from 'react';

// Recharts needs real colour values, not classes, so the chart has to read
// the tokens itself -- and read them again when the theme flips, or a chart
// drawn in light mode keeps light-mode axes on a dark page.
const TOKENS = {
  ink: '--c-ink',
  graphite: '--c-graphite',
  rule: '--c-rule',
  verdigris: '--c-verdigris',
  marker: '--c-marker',
  surface: '--c-surface',
};

function read() {
  if (typeof window === 'undefined') return {};
  const style = getComputedStyle(document.documentElement);
  const out = {};
  for (const [name, variable] of Object.entries(TOKENS)) {
    out[name] = style.getPropertyValue(variable).trim();
  }
  return out;
}

export function useThemeColors() {
  const [colors, setColors] = useState(read);

  useEffect(() => {
    // The theme is a class on <html>, so that is what to watch.
    const observer = new MutationObserver(() => setColors(read()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });
    return () => observer.disconnect();
  }, []);

  return colors;
}

// For a chart with more than one series. A single series is verdigris for the
// leading value and rule for the rest, which is handled at the call site.
export const SERIES = ['#127A6B', '#3A5A8C', '#B8862B', '#7A4E7E', '#5E6762'];
