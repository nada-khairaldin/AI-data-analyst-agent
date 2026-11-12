import React from 'react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer,
} from 'recharts';

// Renders whatever the analysis produced, with no knowledge of the dataset.
//
// The old version hardcoded row.product / row.quantity and dataKey="product",
// so it only worked for one question on one CSV. Columns are derived from the
// rows instead.

const MAX_TABLE_ROWS = 50;

function formatCell(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return value.toLocaleString();
  return String(value);
}

function isNumeric(rows, key) {
  return rows.some((row) => typeof row[key] === 'number');
}

export default function ResultBlock({ resultData, resultKind, chartPlan, chartTitle }) {
  if (resultData === null || resultData === undefined) return null;

  // A scalar: an aggregation with no group_by returns one value, not rows.
  if (resultKind === 'scalar' || !Array.isArray(resultData)) {
    return (
      <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-6 shadow-sm">
        <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">Result</div>
        <div className="text-3xl font-bold text-slate-800 dark:text-white tabular-nums">
          {formatCell(resultData)}
        </div>
      </div>
    );
  }

  if (resultData.length === 0) {
    return (
      <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 text-sm text-slate-500">
        The analysis returned no rows.
      </div>
    );
  }

  // Union of keys, first-seen order, so a row with a missing key cannot drop
  // a column from the header.
  const columns = [];
  for (const row of resultData) {
    for (const key of Object.keys(row)) {
      if (!columns.includes(key)) columns.push(key);
    }
  }

  const showChart = Boolean(chartPlan?.should_plot);
  const x = chartPlan?.x;
  const y = chartPlan?.y;
  const chartable = showChart && columns.includes(x) && columns.includes(y);
  const chartType = chartPlan?.chart_type === 'line' ? 'line' : 'bar';

  // A chart of 200 categories is unreadable; the table still has everything.
  const chartRows = resultData.slice(0, 30);
  const tableRows = resultData.slice(0, MAX_TABLE_ROWS);

  return (
    <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 shadow-sm">
      <div className="flex flex-col md:flex-row gap-8">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
            Results
            <span className="ml-2 text-xs font-normal text-slate-500">
              {resultData.length.toLocaleString()} row{resultData.length === 1 ? '' : 's'}
            </span>
          </h4>
          <div className="overflow-auto max-h-80 border border-slate-100 dark:border-dark-border rounded-lg">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 dark:bg-dark-bg text-slate-500 sticky top-0">
                <tr>
                  {columns.map((key) => (
                    <th
                      key={key}
                      className={`px-3 py-2 font-medium whitespace-nowrap ${
                        isNumeric(resultData, key) ? 'text-right' : ''
                      }`}
                    >
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
                {tableRows.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50 dark:hover:bg-dark-elevated transition-colors">
                    {columns.map((key) => (
                      <td
                        key={key}
                        className={`px-3 py-2 whitespace-nowrap ${
                          isNumeric(resultData, key)
                            ? 'text-right text-slate-600 dark:text-slate-400 tabular-nums'
                            : 'text-slate-700 dark:text-slate-300 font-medium'
                        }`}
                      >
                        {formatCell(row[key])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {resultData.length > MAX_TABLE_ROWS && (
            <p className="text-xs text-slate-500 mt-2">
              Showing the first {MAX_TABLE_ROWS} of {resultData.length.toLocaleString()} rows.
            </p>
          )}
        </div>

        {chartable && (
          <div className="flex-1 h-72 min-w-0 border-t md:border-t-0 md:border-l border-slate-100 dark:border-dark-border pt-6 md:pt-0 md:pl-8">
            <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">
              {chartTitle || `${y} by ${x}`}
            </h4>
            <ResponsiveContainer width="100%" height="88%">
              {chartType === 'line' ? (
                <LineChart data={chartRows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                  <XAxis dataKey={x} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} width={56} />
                  <RechartsTooltip
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: 8, color: '#f1f5f9' }}
                  />
                  <Line type="monotone" dataKey={y} stroke="#38BDF8" strokeWidth={2} dot={false} />
                </LineChart>
              ) : (
                <BarChart data={chartRows} layout="vertical" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#334155" opacity={0.3} />
                  <XAxis type="number" hide />
                  <YAxis
                    dataKey={x}
                    type="category"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    width={110}
                  />
                  <RechartsTooltip
                    cursor={{ fill: 'transparent' }}
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: 8, color: '#f1f5f9' }}
                  />
                  <Bar dataKey={y} fill="#38BDF8" radius={[0, 4, 4, 0]} barSize={14} />
                </BarChart>
              )}
            </ResponsiveContainer>
            {resultData.length > chartRows.length && (
              <p className="text-xs text-slate-500 mt-1">
                First {chartRows.length} of {resultData.length.toLocaleString()}.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
