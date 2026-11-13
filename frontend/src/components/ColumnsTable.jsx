import React from 'react';
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
    <div>
      <div className="overflow-x-auto border-t border-b border-rule">
        <table className="w-full text-sm text-left border-collapse min-w-[620px]">
          <thead>
            <tr className="border-b border-rule text-graphite">
              <th className="px-3 py-1.5 font-normal">Column</th>
              <th className="px-3 py-1.5 font-normal">Type</th>
              <th className="px-3 py-1.5 font-normal">Originally</th>
              <th className="px-3 py-1.5 font-normal text-right">Missing</th>
              <th className="px-3 py-1.5 font-normal">Status</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((column) => {
              const conversion = conversions[column.name];
              return (
                <tr key={column.name} className="border-b border-rule last:border-b-0">
                  <td className="px-3 py-1.5 text-ink whitespace-nowrap">{column.name}</td>
                  <td className="px-3 py-1.5 text-graphite whitespace-nowrap">
                    {readableType(column.dtype)}
                  </td>
                  <td className="px-3 py-1.5 text-graphite whitespace-nowrap">
                    {conversion
                      ? `${readableType(conversion.from)}, ${conversion.successRate}`
                      : 'unchanged'}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular text-ink">
                    {column.missingRate}
                  </td>
                  <td className="px-3 py-1.5 text-graphite">
                    {column.available
                      ? 'Available'
                      : `Excluded${column.exclusionReason ? `, ${column.exclusionReason}` : ''}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-graphite mt-2 tabular">
        {columns.length} columns · {columns.filter((c) => c.available).length} available to the
        analysis
      </p>
    </div>
  );
}
