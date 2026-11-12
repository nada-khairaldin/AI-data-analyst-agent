import React from 'react';
import { CheckCircle2, AlertCircle, Info, XCircle } from 'lucide-react';
import { ChecksSkeleton } from './Skeleton';

// Rendered from the server's ordered `checks` array. Every value here was a
// literal in the mock — customer_phone, 78.4%, order_date — so a different
// CSV told the same story no matter what was in it.

const LEVELS = {
  success: { Icon: CheckCircle2, tone: 'text-success', bar: '' },
  warning: { Icon: AlertCircle, tone: 'text-warning', bar: 'border-l-4 border-warning' },
  info: { Icon: Info, tone: 'text-primary', bar: 'border-l-4 border-primary' },
  error: { Icon: XCircle, tone: 'text-rose-600 dark:text-error', bar: 'border-l-4 border-error' },
};

function Check({ check }) {
  const { Icon, tone, bar } = LEVELS[check.level] || LEVELS.info;

  return (
    <div
      className={`bg-white dark:bg-dark-card rounded-xl border border-slate-200 dark:border-dark-border p-5 shadow-sm ${bar}`}
    >
      <div className="flex items-start gap-3">
        <Icon size={20} className={`${tone} shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-800 dark:text-slate-200">{check.title}</h3>
          {check.summary && (
            <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">{check.summary}</p>
          )}

          {check.excludedColumns?.length > 0 && (
            <ul className="mt-3 space-y-1.5 text-sm">
              {check.excludedColumns.map((column) => (
                <li key={column.name} className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono bg-slate-100 dark:bg-dark-bg px-2 py-0.5 rounded text-slate-700 dark:text-slate-300">
                    {column.name}
                  </span>
                  <span className="text-slate-600 dark:text-slate-400">({column.reason})</span>
                </li>
              ))}
            </ul>
          )}

          {check.conversions?.length > 0 && (
            <ul className="mt-3 space-y-1.5 text-sm">
              {check.conversions.map((conversion) => (
                <li key={conversion.name} className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-slate-700 dark:text-slate-300">
                    {conversion.name}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">
                    {conversion.from} &rarr; {conversion.to}
                  </span>
                  <span className="text-success text-xs">{conversion.successRate}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DataPreparation({ report, isLoading }) {
  if (isLoading || !report) return <ChecksSkeleton />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 text-sm">
        <span className="flex items-center gap-1.5 bg-success/10 text-success px-3 py-1.5 rounded-full font-medium">
          <CheckCircle2 size={14} />
          {report.checksCompleted} checks completed
        </span>
        <span className="flex items-center gap-1.5 bg-warning/10 text-amber-700 dark:text-warning px-3 py-1.5 rounded-full font-medium">
          <AlertCircle size={14} />
          {report.noticeCount} notice{report.noticeCount === 1 ? '' : 's'}
        </span>
        <span className="flex items-center gap-1.5 bg-slate-100 dark:bg-dark-card text-slate-700 dark:text-slate-300 px-3 py-1.5 rounded-full font-medium">
          Quality {report.qualityScore} ({report.qualityLabel})
        </span>
      </div>

      {report.checks?.map((check) => <Check key={check.order} check={check} />)}

      <p className="text-xs text-slate-500 dark:text-slate-400 pt-2">
        Excluded columns remain in the original dataset; they are only left out
        of the analysis.
      </p>
    </div>
  );
}
