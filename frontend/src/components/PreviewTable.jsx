import React from 'react';
import { TableSkeleton } from './Skeleton';

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T[\d:.]+$/;

// Values arrive as JSON, so a date is a string and a missing value is null.
// Both need saying out loud: a blank cell is indistinguishable from an empty
// string, and the whole point of this app is data quality.
function Cell({ value }) {
  if (value === null || value === undefined) {
    return <span className="text-graphite">missing</span>;
  }
  if (typeof value === 'string' && ISO_DATETIME.test(value)) return value.slice(0, 10);
  if (typeof value === 'number') return value.toLocaleString();
  if (typeof value === 'boolean') return String(value);
  return String(value);
}

const isNumeric = (rows, key) => rows.some((row) => typeof row[key] === 'number');

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
    return <p className="text-sm text-graphite">This dataset has no rows to preview.</p>;
  }

  return (
    <div>
      <div className="overflow-x-auto border-t border-b border-rule">
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-rule text-graphite">
              {columns.map((name) => (
                <th
                  key={name}
                  className={`px-3 py-1.5 font-normal whitespace-nowrap ${
                    isNumeric(rows, name) ? 'text-right' : ''
                  }`}
                >
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-b border-rule last:border-b-0">
                {columns.map((name) => (
                  <td
                    key={name}
                    className={`px-3 py-1.5 whitespace-nowrap text-ink ${
                      isNumeric(rows, name) ? 'text-right tabular' : ''
                    }`}
                  >
                    <Cell value={row[name]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-graphite mt-2 tabular">
        First {rows.length} of {preview.totalRows?.toLocaleString()} rows
      </p>
    </div>
  );
}
