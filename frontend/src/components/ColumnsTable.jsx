import React from 'react';
import { CheckCircle2, MinusCircle } from 'lucide-react';
import { TableSkeleton } from './Skeleton';

// The columns endpoint reports the dtype the analysis sees. What it was
// before is only knowable from the report's conversion list, so the two are
// joined here rather than asking the backend for a field it does not store.

function readableType(dtype) {
  if (!dtype) return 'unknown';
  if (dtype.startsWith('datetime')) return 'date';
  if (dtype.startsWith('int') || dtype.startsWith('Int')) return 'integer';
  if (dtype.startsWith('float') || dtype.startsWith('Float')) return 'number';
  if (dtype === 'str' || dtype.startsWith('string') || dtype === 'object') return 'text';
  if (dtype.startsWith('bool')) return 'true/false';
  return dtype;
}

export default function ColumnsTable({ columns, report, isLoading }) {
  if (isLoading || !columns) return <TableSkeleton rows={8} cols={5} />;

  const conversions = {};
  for (const check of report?.checks || []) {
    for (const conversion of check.conversions || []) {
      conversions[conversion.name] = conversion;
    }
  }

  return (
    <div className="bg-white dark:bg-dark-card rounded-xl border border-slate-200 dark:border-dark-border shadow-sm overflow-hidden">
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-slate-50 dark:bg-dark-bg border-b border-slate-200 dark:border-dark-border">
            <tr className="text-left text-xs uppercase tracking-wider text-slate-600 dark:text-slate-400">
              <th className="px-4 py-3 font-semibold">Column</th>
              <th className="px-4 py-3 font-semibold">Type</th>
              <th className="px-4 py-3 font-semibold">Originally</th>
              <th className="px-4 py-3 font-semibold text-right">Missing</th>
              <th className="px-4 py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
            {columns.map((column) => {
              const conversion = conversions[column.name];
              return (
                <tr
                  key={column.name}
                  className={`hover:bg-slate-50 dark:hover:bg-dark-elevated transition-colors ${
                    column.available ? '' : 'bg-slate-50/60 dark:bg-dark-bg/40'
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-slate-800 dark:text-slate-200 whitespace-nowrap">
                    {column.name}
                  </td>
                  <td className="px-4 py-3 text-slate-700 dark:text-slate-300 whitespace-nowrap">
                    {readableType(column.dtype)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {conversion ? (
                      <span className="text-slate-600 dark:text-slate-400">
                        {readableType(conversion.from)}
                        <span className="text-success text-xs ml-2">
                          {conversion.successRate}
                        </span>
                      </span>
                    ) : (
                      <span className="text-slate-400 dark:text-slate-500">unchanged</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700 dark:text-slate-300">
                    {column.missingRate}
                  </td>
                  <td className="px-4 py-3">
                    {column.available ? (
                      <span className="inline-flex items-center gap-1.5 text-success">
                        <CheckCircle2 size={14} /> Available
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 flex-wrap text-amber-700 dark:text-warning">
                        <MinusCircle size={14} /> Excluded
                        {column.exclusionReason && (
                          <span className="text-slate-600 dark:text-slate-400 text-xs">
                            ({column.exclusionReason})
                          </span>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-dark-border">
        {columns.length} columns · {columns.filter((c) => c.available).length} available to the
        analysis
      </div>
    </div>
  );
}
