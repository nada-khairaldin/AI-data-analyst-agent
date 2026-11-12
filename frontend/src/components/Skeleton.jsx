import React from 'react';

// A skeleton is only useful if it has the shape of what replaces it; a grey
// box of the wrong size moves the layout on arrival and reads as a glitch.

export function Bar({ className = '' }) {
  return (
    <div className={`animate-pulse rounded bg-slate-200 dark:bg-dark-elevated ${className}`} />
  );
}

export function CardSkeleton({ lines = 3 }) {
  return (
    <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
      <Bar className="h-4 w-40 mb-5" />
      <div className="space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <Bar key={i} className={`h-3 ${i % 2 ? 'w-4/5' : 'w-full'}`} />
        ))}
      </div>
    </div>
  );
}

export function ChecksSkeleton({ count = 6 }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Bar className="h-8 w-40 rounded-full" />
        <Bar className="h-8 w-28 rounded-full" />
        <Bar className="h-8 w-36 rounded-full" />
      </div>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-white dark:bg-dark-card rounded-xl border border-slate-200 dark:border-dark-border p-5 shadow-sm flex items-start gap-3"
        >
          <Bar className="h-5 w-5 rounded-full shrink-0" />
          <div className="flex-1 space-y-2.5">
            <Bar className="h-4 w-48" />
            <Bar className="h-3 w-3/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 8, cols = 5 }) {
  return (
    <div className="bg-white dark:bg-dark-card rounded-xl border border-slate-200 dark:border-dark-border overflow-hidden shadow-sm">
      <div className="flex gap-4 px-4 py-3 border-b border-slate-200 dark:border-dark-border bg-slate-50 dark:bg-dark-bg">
        {Array.from({ length: cols }).map((_, i) => (
          <Bar key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="flex gap-4 px-4 py-3 border-b border-slate-100 dark:border-dark-border last:border-0"
        >
          {Array.from({ length: cols }).map((_, c) => (
            <Bar key={c} className={`h-3 flex-1 ${(r + c) % 3 === 0 ? 'opacity-60' : ''}`} />
          ))}
        </div>
      ))}
    </div>
  );
}
