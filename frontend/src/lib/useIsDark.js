import { useEffect, useState } from 'react';

// Recharts needs real colour values, not classes, so a chart has to know
// which theme it is in. The old chart hardcoded dark-mode greys, which is
// why its axes and tooltip looked wrong on the light screens.
export function useIsDark() {
  const [isDark, setIsDark] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark'),
  );

  useEffect(() => {
    const read = () => setIsDark(document.documentElement.classList.contains('dark'));
    read();
    // The theme is a class on <html>, so that is what to watch.
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

export const MARKER_YELLOW = '#F2D45C';

export function chartColors(isDark) {
  return isDark
    ? { grid: '#334155', tick: '#94a3b8', bar: '#38BDF8', dim: '#475569',
        tooltipBg: '#111C2E', tooltipBorder: '#24344D', tooltipText: '#f1f5f9' }
    : { grid: '#CBD5E1', tick: '#64748b', bar: '#0EA5E9', dim: '#CBD5E1',
        tooltipBg: '#ffffff', tooltipBorder: '#e2e8f0', tooltipText: '#0f172a' };
}
