import React from 'react';

/**
 * One worked example, shown before anything is uploaded. Entirely static
 * markup — no API call, no numbers pretending to come from the user's data.
 *
 * It replaced three icons captioned "No coding required", "Clear & visual
 * results", "Full transparency", which asserted the product was good
 * without showing anything. This shows the actual shape of an answer: a
 * sentence with the figure marked, and the chart it came from.
 */

// Illustrative figures for the example, not a computed result.
const BARS = [
  { label: 'Germany', value: 617940, lead: true },
  { label: 'France', value: 441300 },
  { label: 'Spain', value: 352100 },
];

const MAX = Math.max(...BARS.map((bar) => bar.value));

export default function ExampleAnswer() {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-500 mb-3">
        For example
      </p>

      <div className="flex justify-end">
        <p className="max-w-[85%] bg-slate-200/60 dark:bg-white/10 text-slate-800 dark:text-white px-3.5 py-2 rounded-2xl rounded-tr-sm text-sm">
          Which country had the highest revenue in 2024?
        </p>
      </div>

      <div className="mt-3 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-4">
        <p className="text-sm text-slate-800 dark:text-slate-200">
          Germany, with{' '}
          {/* The marker is the one loud thing in the interface, and it only
              ever lands on the figure that answers the question. */}
          <mark className="bg-[#F2D45C] text-[#1D2321] rounded-sm px-1 py-0.5 font-medium">
            617,940
          </mark>{' '}
          in revenue.
        </p>

        <ul className="mt-3 space-y-1.5">
          {BARS.map((bar) => (
            <li key={bar.label} className="flex items-center gap-2.5 text-xs">
              <span className="w-16 shrink-0 text-slate-600 dark:text-slate-400">
                {bar.label}
              </span>
              <span className="flex-1 h-2.5 bg-slate-100 dark:bg-dark-bg rounded-sm overflow-hidden">
                <span
                  className={`block h-full rounded-sm ${
                    bar.lead ? 'bg-[#F2D45C]' : 'bg-slate-300 dark:bg-slate-600'
                  }`}
                  style={{ width: `${(bar.value / MAX) * 100}%` }}
                />
              </span>
              <span className="w-16 shrink-0 text-right tabular-nums text-slate-600 dark:text-slate-400">
                {bar.value.toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
