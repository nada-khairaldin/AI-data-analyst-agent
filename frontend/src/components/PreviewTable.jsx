import React from 'react';
import { TableSkeleton } from './Skeleton';

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T[\d:.]+$/;

// Values arrive as JSON, so a date is a string and a missing value is null.
// Both need saying out loud: a blank cell is indistinguishable from an empty
// string, and the whole point of this app is data quality.
function Cell({ value }) {
  if (value === null || value === undefined) {
    return <span className="text-slate-400 dark:text-slate-500 italic">missing</span>;
  }
  if (typeof value === 'string' && ISO_DATETIME.test(value)) {
    return <span className="tabular-nums">{value.slice(0, 10)}</span>;
  }
  if (typeof value === 'number') {
    return <span className="tabular-nums">{value.toLocaleString()}</span>;
  }
  if (typeof value === 'boolean') return String(value);
  return String(value);
}

export default function PreviewTable({ preview, isLoading }) {
  if (isLoading || !preview) return <TableSkeleton rows={10} cols={6} />;

  const rows = preview.rows || [];
  // The endpoint's `columns` is the authority on order; fall back to the first
  // row's keys if it ever comes back short.
  const columns =
    preview.columns?.length === Object.keys(rows[0] || {}).length
      ? preview.columns
      : Object.keys(rows[0] || {});

  if (rows.length === 0) {
    return (
      <div className="bg-white dark:bg-dark-card rounded-xl border border-slate-200 dark:border-dark-border p-8 text-center text-slate-600 dark:text-slate-400">
        This dataset has no rows to preview.
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-card rounded-xl border border-slate-200 dark:border-dark-border shadow-sm overflow-hidden">
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-dark-bg border-b border-slate-200 dark:border-dark-border">
            <tr className="text-left text-xs uppercase tracking-wider text-slate-600 dark:text-slate-400">
              {columns.map((name) => (
                <th key={name} className="px-4 py-3 font-semibold whitespace-nowrap font-mono normal-case">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
            {rows.map((row, index) => (
              <tr
                key={index}
                className="hover:bg-slate-50 dark:hover:bg-dark-elevated transition-colors"
              >
                {columns.map((name) => (
                  <td
                    key={name}
                    className="px-4 py-2.5 whitespace-nowrap text-slate-700 dark:text-slate-300"
                  >
                    <Cell value={row[name]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-dark-border">
        First {rows.length} of {preview.totalRows?.toLocaleString()} rows
      </div>
    </div>
  );
}
