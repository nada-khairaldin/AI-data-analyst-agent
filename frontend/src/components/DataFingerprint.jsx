import React from 'react';

/**
 * A 40x40 mark drawn from the dataset's own columns: one bar per column,
 * as tall as the share of that column that is actually present.
 *
 * It replaces a generic file glyph, which looked the same for every CSV. Two
 * datasets now look different at a glance, and a gappy one looks gappy.
 */

const MAX_BARS = 16;
// The upload derives these for "per month" questions. They are the app's
// columns, not the user's, and they would pad every fingerprint identically.
const DERIVED = /_(year|month)$/;

const VIEW = 40;
const PAD = 2;
const BASELINE = VIEW - PAD;      // all bars sit on this line
const FULL = VIEW - PAD * 2;      // a complete, nothing-missing column
const MAX_BAR_WIDTH = 4;          // so three columns are not three slabs
const MIN_BAR_HEIGHT = 1.5;       // a near-empty column still reads as a bar

function kindOf(dtype = '') {
  if (/^(datetime|date|timestamp)/.test(dtype)) return 'date';
  if (/^(u?int|float|Int|Float|decimal|number)/.test(dtype)) return 'numeric';
  return 'text';
}

// "0.0%" -> 0, "75.0%" -> 0.75. Anything unparseable counts as complete
// rather than drawing a column as empty on a bad read.
function missingRatio(value) {
  const parsed = Number.parseFloat(String(value ?? '').replace('%', ''));
  return Number.isFinite(parsed) ? Math.min(Math.max(parsed / 100, 0), 1) : 0;
}

function describe(columns) {
  const counts = { numeric: 0, date: 0, text: 0, excluded: 0 };
  for (const column of columns) {
    if (!column.available) counts.excluded += 1;
    else counts[kindOf(column.dtype)] += 1;
  }
  const parts = [];
  if (counts.numeric) parts.push(`${counts.numeric} numeric`);
  if (counts.date) parts.push(`${counts.date} date${counts.date === 1 ? '' : 's'}`);
  if (counts.text) parts.push(`${counts.text} text`);
  if (counts.excluded) parts.push(`${counts.excluded} excluded`);

  const total = columns.length;
  const head = `${total} column${total === 1 ? '' : 's'}`;
  return parts.length ? `${head}: ${parts.join(', ')}` : head;
}

const FILLS = {
  numeric: 'fill-slate-800 dark:fill-slate-100',
  date: 'fill-primary',
  text: 'fill-slate-500 dark:fill-slate-400',
};

export default function DataFingerprint({ columns, size = 40, className = '' }) {
  if (!Array.isArray(columns) || columns.length === 0) return null;

  const usable = columns.filter((column) => column?.name && !DERIVED.test(column.name));
  if (usable.length === 0) return null;

  const shown = usable.slice(0, MAX_BARS);
  const label = describe(usable);

  // Equal widths and gaps, the gap half a bar wide. Solving
  // n*w + (n-1)*(w/2) = FULL for w keeps the group exactly FULL wide at any
  // count, and the cap stops a three-column dataset becoming three slabs.
  const n = shown.length;
  const width = Math.min(FULL / (1.5 * n - 0.5), MAX_BAR_WIDTH);
  const gap = width / 2;
  const groupWidth = n * width + (n - 1) * gap;
  const left = (VIEW - groupWidth) / 2;

  return (
    <svg
      viewBox={`0 0 ${VIEW} ${VIEW}`}
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={label}
    >
      <title>{label}</title>
      {shown.map((column, index) => {
        const x = left + index * (width + gap);

        // An excluded column is drawn as the space it would have taken:
        // full height, no fill, dashed. It is not missing data, it is data
        // the analysis will not touch.
        if (!column.available) {
          return (
            <rect
              key={column.name}
              x={x}
              y={PAD}
              width={width}
              height={FULL}
              rx={width / 3}
              fill="none"
              strokeWidth="0.6"
              strokeDasharray="1.6 1.4"
              className="stroke-slate-400 dark:stroke-slate-500"
            />
          );
        }

        const height = Math.max(FULL * (1 - missingRatio(column.missingRate)), MIN_BAR_HEIGHT);
        return (
          <rect
            key={column.name}
            x={x}
            y={BASELINE - height}
            width={width}
            height={height}
            rx={width / 3}
            className={FILLS[kindOf(column.dtype)]}
          />
        );
      })}
    </svg>
  );
}
