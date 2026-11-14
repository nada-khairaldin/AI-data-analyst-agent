import React, { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import {
  BarChart, Bar, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer,
} from 'recharts';
import { useIsDark, chartColors, MARKER_YELLOW } from '../lib/useIsDark';
import { splitOnValue, formatNumber } from '../lib/figure';
import { readShape, rowLabel, topRows, chartCaption, MAX_BARS } from '../lib/resultShape';

/**
 * One card for every answer: the live stream, a saved reply reopened later,
 * and the worked example on the welcome screen all render through here with
 * the same props. Two renderers would drift, and the example would start
 * promising a layout the real answers no longer have.
 *
 * `text` is what to show (a partial sentence while the reveal runs) and
 * `fullText` what to analyse, so the marker can be positioned before the
 * reveal reaches it and appear exactly when it does.
 */

const MARKER = 'bg-[#F2D45C] text-[#1D2321] rounded-sm px-1 py-0.5';

function Sentence({ text, fullText, figureValue }) {
  const complete = fullText ?? text ?? '';
  const shown = text ?? '';
  const split = typeof figureValue === 'number' ? splitOnValue(complete, figureValue) : null;

  // No match means no marker: a highlight on the wrong number is worse than
  // none at all.
  if (!split) {
    return (
      <p dir="auto" className="text-[15px] leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap">
        {shown}
      </p>
    );
  }

  const revealedThrough = split.before.length + split.figure.length;
  if (shown.length < revealedThrough) {
    // The reveal has not reached the figure yet, so it is still plain text.
    return (
      <p dir="auto" className="text-[15px] leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap">
        {shown}
      </p>
    );
  }

  return (
    <p dir="auto" className="text-[15px] leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap">
      {split.before}
      <mark className={`${MARKER} font-medium`}>{split.figure}</mark>
      {shown.slice(revealedThrough)}
    </p>
  );
}

function Bars({ rows, shape, hidden }) {
  const colors = chartColors(useIsDark());
  // Recharts needs one field to label a bar, and a grouped result names a
  // row with several columns at once.
  const data = rows.map((row) => ({ ...row, __label: rowLabel(row, shape.groupColumns) }));
  const longest = Math.max(...data.map((row) => row.__label.length), 8);
  const axisWidth = Math.min(Math.max(longest * 6.5, 80), 190);

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(data.length * 28 + 16, 140)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={colors.grid} opacity={0.4} />
          <XAxis type="number" hide />
          <YAxis
            dataKey="__label"
            type="category"
            axisLine={false}
            tickLine={false}
            tick={{ fill: colors.tick, fontSize: 11 }}
            width={axisWidth}
          />
          <RechartsTooltip
            cursor={{ fill: 'transparent' }}
            formatter={(value) => formatNumber(value)}
            contentStyle={{
              backgroundColor: colors.tooltipBg,
              borderColor: colors.tooltipBorder,
              borderRadius: 8,
              color: colors.tooltipText,
            }}
          />
          <Bar dataKey={shape.measure} radius={[0, 4, 4, 0]} barSize={14}
            label={{ position: 'right', fill: colors.tick, fontSize: 11,
              formatter: (value) => formatNumber(value) }}>
            {/* The leading bar carries the marker, the rest stay quiet. */}
            {data.map((row, index) => (
              <Cell key={row.__label} fill={index === 0 ? MARKER_YELLOW : colors.bar} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {hidden > 0 && (
        <p className="mt-1 text-xs text-slate-500">and {hidden.toLocaleString()} more</p>
      )}
    </div>
  );
}

function TimeChart({ resultData, shape }) {
  const colors = chartColors(useIsDark());
  const key = shape.timeColumn;
  const points = resultData.filter((row) => typeof row[shape.measure] === 'number');
  if (points.length < 2) {
    return <Bars rows={points} shape={shape} hidden={0} />;
  }

  const max = Math.max(...points.map((row) => row[shape.measure]));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={points} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} opacity={0.4} />
        <XAxis dataKey={key} tick={{ fill: colors.tick, fontSize: 11 }} />
        <YAxis tick={{ fill: colors.tick, fontSize: 11 }} width={62}
          tickFormatter={(value) => formatNumber(value)} />
        <RechartsTooltip
          formatter={(value) => formatNumber(value)}
          contentStyle={{
            backgroundColor: colors.tooltipBg,
            borderColor: colors.tooltipBorder,
            borderRadius: 8,
            color: colors.tooltipText,
          }}
        />
        <Line
          type="monotone"
          dataKey={shape.measure}
          stroke={colors.bar}
          strokeWidth={2}
          // The peak is the only marked point: a dot on every month is noise.
          dot={(props) =>
            props.payload[shape.measure] === max ? (
              <circle key={props.index} cx={props.cx} cy={props.cy} r={5} fill={MARKER_YELLOW} />
            ) : null
          }
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ResultTable({ resultData, shape }) {
  const rows = resultData.slice(0, 50);
  return (
    <div className="mt-2 overflow-auto max-h-72 border border-slate-200 dark:border-dark-border rounded-lg">
      <table className="w-full text-sm text-left">
        <thead className="bg-slate-50 dark:bg-dark-bg text-slate-500 sticky top-0">
          <tr>
            {shape.columns.map((key) => (
              <th key={key} className={`px-3 py-2 font-medium whitespace-nowrap ${key === shape.measure ? 'text-right' : ''}`}>
                {key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
          {rows.map((row, i) => (
            <tr key={i}>
              {shape.columns.map((key) => (
                <td
                  key={key}
                  dir="auto"
                  className={`px-3 py-2 whitespace-nowrap ${
                    key === shape.measure
                      ? 'text-right tabular-nums text-slate-600 dark:text-slate-400'
                      : 'text-slate-700 dark:text-slate-300'
                  }`}
                >
                  {typeof row[key] === 'number' ? formatNumber(row[key]) : String(row[key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {resultData.length > rows.length && (
        <p className="px-3 py-2 text-xs text-slate-500">
          Showing the first {rows.length} of {resultData.length.toLocaleString()} rows.
        </p>
      )}
    </div>
  );
}

export default function AnswerCard({ text, fullText, resultData, resultKind, plan }) {
  const [showTable, setShowTable] = useState(true);
  const shape = readShape(resultData, resultKind);

  if (shape.kind === 'scalar') {
    const value = typeof shape.value === 'number' ? shape.value : null;
    return (
      <div className="space-y-3">
        <Sentence text={text} fullText={fullText} figureValue={value} />
        <div className="text-3xl font-bold tabular-nums">
          <mark className={MARKER}>{formatNumber(shape.value)}</mark>
        </div>
      </div>
    );
  }

  if (shape.kind === 'empty') {
    return (
      <div className="space-y-3">
        <Sentence text={text} fullText={fullText} />
        <p className="text-sm text-slate-500">The analysis returned no rows.</p>
      </div>
    );
  }

  const chartable = shape.kind === 'category' || shape.kind === 'time';
  // The sentence reports the first row of the result; that is the figure the
  // marker belongs on.
  const figureValue = shape.measure ? resultData[0]?.[shape.measure] : undefined;
  const caption = chartable ? chartCaption(plan, shape) : null;
  const { rows, hidden } = chartable && shape.kind === 'category'
    ? topRows(resultData, shape.measure, MAX_BARS)
    : { rows: [], hidden: 0 };

  return (
    // Sentence, then the chart at full width, then the table behind a
    // toggle. Side by side, neither had room: a two-column label like
    // "Germany, Docking Station" needs the width.
    <div className="space-y-3">
      <Sentence text={text} fullText={fullText} figureValue={figureValue} />

      {chartable && (
        <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-4">
          {caption && (
            <p dir="auto" className="text-xs text-slate-500 mb-3">{caption}</p>
          )}
          {shape.kind === 'time' ? (
            <TimeChart resultData={resultData} shape={shape} />
          ) : (
            <Bars rows={rows} shape={shape} hidden={hidden} />
          )}
        </div>
      )}

      <div>
        <button
          type="button"
          onClick={() => setShowTable((open) => !open)}
          className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
        >
          <ChevronRight size={15} className={showTable ? 'rotate-90 transition-transform' : 'transition-transform'} />
          {showTable ? 'Hide table' : 'Show table'}
          <span className="text-slate-400">
            ({resultData.length.toLocaleString()} row{resultData.length === 1 ? '' : 's'})
          </span>
        </button>
        {showTable && <ResultTable resultData={resultData} shape={shape} />}
      </div>
    </div>
  );
}
