import React from 'react';
import { AlertTriangle, FileText, UploadCloud, X } from 'lucide-react';

// `--color-error` is rose-400: fine as a fill or a border, far too light for
// text on white (~2.9:1). Text uses rose-600 in light mode and the token in
// dark mode, which is the readable pairing in both.

function percent(value, fallback = 0) {
  const parsed = Number.parseFloat(String(value ?? '').replace('%', ''));
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function DatasetRejected({
  filename,
  fileSize,
  missingRate,
  maxAllowed = '40%',
  reasons = [],
  onUploadAnother,
  onClose,
}) {
  const actual = percent(missingRate);
  const limit = percent(maxAllowed, 40);

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 h-full overflow-y-auto bg-slate-50 dark:bg-dark-bg relative">
      {onClose && (
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute top-6 right-6 p-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-200/60 dark:text-slate-400 dark:hover:text-white dark:hover:bg-dark-elevated transition-colors"
        >
          <X size={22} />
        </button>
      )}

      <div className="max-w-lg w-full bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border shadow-lg overflow-hidden">
        <div className="p-7 flex flex-col items-center text-center border-b border-slate-200 dark:border-dark-border">
          <div className="w-14 h-14 bg-rose-100 dark:bg-error/15 text-rose-600 dark:text-error rounded-full flex items-center justify-center mb-5">
            <AlertTriangle size={28} />
          </div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            This file can&apos;t be analysed
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 max-w-sm">
            Too much of it is missing for any answer to be trustworthy, so it was
            not saved.
          </p>
        </div>

        <div className="p-6 space-y-6">
          <div className="flex items-center gap-3 bg-slate-50 dark:bg-dark-bg border border-slate-200 dark:border-dark-border rounded-xl p-4">
            <FileText size={22} className="text-slate-500 dark:text-slate-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="font-medium text-slate-900 dark:text-slate-100 truncate">
                {filename}
              </div>
              {fileSize && (
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">{fileSize}</div>
              )}
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-3">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Missing values
              </span>
              <span className="text-lg font-bold text-rose-600 dark:text-error tabular-nums">
                {missingRate}
              </span>
            </div>

            {/* The bar is the whole point of this screen: it shows how far past
                the limit the file is, not just that it failed. */}
            <div className="relative h-3 w-full bg-slate-200 dark:bg-dark-bg rounded-full overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 bg-rose-500 dark:bg-error rounded-full"
                style={{ width: `${Math.min(actual, 100)}%` }}
              />
              <div
                className="absolute inset-y-0 w-0.5 bg-slate-700 dark:bg-slate-200"
                style={{ left: `${Math.min(limit, 100)}%` }}
              />
            </div>

            <div className="relative mt-2 h-5 text-xs text-slate-600 dark:text-slate-400">
              <span className="absolute left-0">0%</span>
              <span
                className="absolute -translate-x-1/2 whitespace-nowrap font-medium text-slate-700 dark:text-slate-300"
                style={{ left: `${Math.min(limit, 100)}%` }}
              >
                limit {maxAllowed}
              </span>
              <span className="absolute right-0">100%</span>
            </div>
          </div>

          {reasons.length > 0 && (
            <ul className="space-y-2">
              {reasons.map((reason) => (
                <li
                  key={reason}
                  className="flex items-start gap-2.5 text-sm bg-rose-50 dark:bg-error/10 border border-rose-200 dark:border-error/30 rounded-lg p-3 text-slate-800 dark:text-slate-200"
                >
                  <AlertTriangle
                    size={15}
                    className="mt-0.5 shrink-0 text-rose-600 dark:text-error"
                  />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="px-6 py-5 bg-slate-50 dark:bg-dark-bg border-t border-slate-200 dark:border-dark-border flex justify-center">
          <button
            onClick={onUploadAnother}
            className="flex items-center gap-2 px-6 py-2.5 bg-primary hover:brightness-110 text-slate-900 rounded-lg font-semibold transition-all shadow-sm"
          >
            <UploadCloud size={18} />
            Upload another file
          </button>
        </div>
      </div>
    </div>
  );
}
