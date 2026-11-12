import React from 'react';
import { ArrowLeft, CheckCircle2, AlertCircle, Info, XCircle } from 'lucide-react';

// Rendered from the server's ordered `checks` array. Every value in this view
// was a literal before — customer_phone, 78.4%, order_date, 2.1%, "6 checks
// completed" — so a different CSV showed the same story.

const LEVELS = {
  success: { Icon: CheckCircle2, tone: 'text-success', bar: '' },
  warning: { Icon: AlertCircle, tone: 'text-warning', bar: 'border-l-4 border-warning' },
  info: { Icon: Info, tone: 'text-primary', bar: 'border-l-4 border-primary' },
  error: { Icon: XCircle, tone: 'text-error', bar: 'border-l-4 border-error' },
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
                  <span className="text-slate-500">({column.reason})</span>
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
                  <span className="text-slate-400">
                    {conversion.from} → {conversion.to}
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

export default function PreprocessingReport({ dataset, report, onBack }) {
  if (!dataset) return null;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary overflow-hidden">
      <header className="bg-white dark:bg-dark-sidebar border-b border-slate-200 dark:border-dark-border px-6 py-4 shrink-0">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-white transition-colors mb-2"
        >
          <ArrowLeft size={16} /> Back to overview
        </button>
        <h1 className="text-xl font-bold text-slate-800 dark:text-white">Data preparation</h1>
        <p className="text-sm text-slate-500 mt-1">
          {dataset.name} · {dataset.rowCount?.toLocaleString()} rows · {dataset.colCount} columns
        </p>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {!report && <div className="text-sm text-slate-500">Loading report…</div>}

          {report && (
            <>
              <div className="flex flex-wrap gap-3 text-sm">
                <span className="flex items-center gap-1.5 bg-success/10 text-success px-3 py-1.5 rounded-full font-medium">
                  <CheckCircle2 size={14} />
                  {report.checksCompleted} checks completed
                </span>
                <span className="flex items-center gap-1.5 bg-warning/10 text-warning px-3 py-1.5 rounded-full font-medium">
                  <AlertCircle size={14} />
                  {report.noticeCount} notice{report.noticeCount === 1 ? '' : 's'}
                </span>
                <span className="flex items-center gap-1.5 bg-slate-100 dark:bg-dark-card text-slate-600 dark:text-slate-300 px-3 py-1.5 rounded-full font-medium">
                  Quality {report.qualityScore} ({report.qualityLabel})
                </span>
              </div>

              {report.checks?.map((check) => <Check key={check.order} check={check} />)}

              <p className="text-xs text-slate-500 pt-2">
                Excluded columns remain in the original dataset; they are only left
                out of the analysis.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
