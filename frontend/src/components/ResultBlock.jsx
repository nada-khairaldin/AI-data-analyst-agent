import React from 'react';
import {
  BarChart, Bar, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer,
} from 'recharts';
import { useThemeColors } from '../lib/useThemeColors';

// Renders whatever the analysis produced, with no knowledge of the dataset.
// Columns are derived from the rows, never hardcoded.

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
  const colors = useThemeColors();

  if (resultData === null || resultData === undefined) return null;

  // A scalar: an aggregation with no group_by returns one value, not rows.
  // It is the whole answer, so it gets the marker.
  if (resultKind === 'scalar' || !Array.isArray(resultData)) {
    return (
      <div>
        <div className="text-sm text-graphite mb-1.5">Result</div>
        <div className="text-3xl text-ink tabular-nums">
          <mark className="marker">{formatCell(resultData)}</mark>
        </div>
      </div>
    );
  }

  if (resultData.length === 0) {
    return <p className="text-sm text-graphite">The analysis returned no rows.</p>;
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

  // The leading value, not row 0: a grouped result is often ordered by its
  // key, so the biggest bar is not necessarily the first one.
  const peak = chartable
    ? Math.max(...chartRows.map((row) => (typeof row[y] === 'number' ? row[y] : -Infinity)))
    : null;

  const axisTick = { fill: colors.graphite, fontSize: 11 };
  const tooltipStyle = {
    backgroundColor: colors.surface,
    border: `1px solid ${colors.rule}`,
    borderRadius: 4,
    color: colors.ink,
    fontSize: 12,
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 lg:gap-8">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-graphite mb-1.5">
          Result
          <span className="ml-2">
            {resultData.length.toLocaleString()} row{resultData.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="overflow-auto max-h-80 border-t border-b border-rule">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="sticky top-0 bg-paper">
              <tr className="border-b border-rule">
                {columns.map((key) => (
                  <th
                    key={key}
                    className={`px-3 py-1.5 font-normal text-graphite whitespace-nowrap ${
                      isNumeric(resultData, key) ? 'text-right' : ''
                    }`}
                  >
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row, i) => (
                // The first row is the answer the question asked for, so it
                // carries the marker. Rows below it are the evidence.
                <tr
                  key={i}
                  className={`border-b border-rule last:border-b-0 ${
                    i === 0 ? 'bg-marker/55' : ''
                  }`}
                >
                  {columns.map((key) => (
                    <td
                      key={key}
                      className={`px-3 py-1.5 whitespace-nowrap ${
                        isNumeric(resultData, key)
                          ? 'text-right tabular-nums'
                          : 'text-left'
                      } ${i === 0 ? 'text-[#1D2321]' : 'text-ink'}`}
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
          <p className="text-xs text-graphite mt-1.5">
            First {MAX_TABLE_ROWS} of {resultData.length.toLocaleString()} rows.
          </p>
        )}
      </div>

      {chartable && (
        <div className="flex-1 h-72 min-w-0">
          <div className="text-sm text-graphite mb-1.5">{chartTitle || `${y} by ${x}`}</div>
          <ResponsiveContainer width="100%" height="88%">
            {chartType === 'line' ? (
              <LineChart data={chartRows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={colors.rule} vertical={false} />
                <XAxis dataKey={x} tick={axisTick} stroke={colors.rule} />
                <YAxis tick={axisTick} stroke={colors.rule} width={56} />
                <RechartsTooltip contentStyle={tooltipStyle} />
                <Line
                  type="monotone"
                  dataKey={y}
                  stroke={colors.verdigris}
                  strokeWidth={1.5}
                  dot={false}
                />
              </LineChart>
            ) : (
              <BarChart data={chartRows} layout="vertical" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={colors.rule} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey={x}
                  type="category"
                  axisLine={false}
                  tickLine={false}
                  tick={axisTick}
                  width={110}
                />
                <RechartsTooltip cursor={{ fill: 'transparent' }} contentStyle={tooltipStyle} />
                <Bar dataKey={y} barSize={12}>
                  {chartRows.map((row, i) => (
                    <Cell
                      key={i}
                      fill={row[y] === peak ? colors.verdigris : colors.rule}
                    />
                  ))}
                </Bar>
              </BarChart>
            )}
          </ResponsiveContainer>
          {resultData.length > chartRows.length && (
            <p className="text-xs text-graphite mt-1">
              First {chartRows.length} of {resultData.length.toLocaleString()}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
