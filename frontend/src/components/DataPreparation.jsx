import React from 'react';
import { ChecksSkeleton } from './Skeleton';

// Rendered from the server's ordered `checks` array. Every value here was a
// literal in the mock — customer_phone, 78.4%, order_date — so a different
// CSV told the same story no matter what was in it.
//
// A level is said in words, not in a coloured icon: "Needs attention" reads
// the same to someone who cannot tell the warning amber from the info blue.
const LEVELS = {
  success: '',
  info: 'Changed',
  warning: 'Needs attention',
  error: 'Problem',
};

function Check({ check }) {
  const note = LEVELS[check.level] ?? '';

  return (
    <div className="py-4 border-b border-rule">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-ink">{check.title}</h3>
        {note && <span className="text-sm text-graphite shrink-0">{note}</span>}
      </div>

      {check.summary && <p className="text-sm text-graphite mt-1">{check.summary}</p>}

      {check.excludedColumns?.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {check.excludedColumns.map((column) => (
            <li key={column.name} className="flex flex-wrap items-baseline gap-2">
              <span className="text-ink">{column.name}</span>
              <span className="text-graphite">{column.reason}</span>
            </li>
          ))}
        </ul>
      )}

      {check.conversions?.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {check.conversions.map((conversion) => (
            <li key={conversion.name} className="flex flex-wrap items-baseline gap-2">
              <span className="text-ink">{conversion.name}</span>
              <span className="text-graphite">
                {conversion.from} to {conversion.to}
              </span>
              <span className="text-graphite tabular">{conversion.successRate}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function DataPreparation({ report, isLoading }) {
  if (isLoading || !report) return <ChecksSkeleton />;

  return (
    <div>
      <p className="text-sm text-graphite tabular">
        {report.checksCompleted} checks · {report.noticeCount} notice
        {report.noticeCount === 1 ? '' : 's'} · quality {report.qualityScore} ({report.qualityLabel})
      </p>

      <div className="mt-4 border-t border-rule">
        {report.checks?.map((check) => <Check key={check.order} check={check} />)}
      </div>

      <p className="text-sm text-graphite mt-4">
        Excluded columns stay in the original file; they are only left out of
        the analysis.
      </p>
    </div>
  );
}
