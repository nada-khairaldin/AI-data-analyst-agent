import React, { useState } from 'react';
import { ChevronRight } from 'lucide-react';
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
  const max = Math.max(...rows.map((row) => row[shape.measure] ?? 0), 0) || 1;

  return (
    <div>
      <ul className="space-y-1.5">
        {rows.map((row, index) => (
          <li key={rowLabel(row, shape.groupColumns)} className="flex items-center gap-2.5 text-xs">
            <span
              dir="auto"
              className="w-36 shrink-0 truncate text-slate-600 dark:text-slate-400"
              title={rowLabel(row, shape.groupColumns)}
            >
              {rowLabel(row, shape.groupColumns)}
            </span>
            <span className="flex-1 h-2.5 bg-slate-100 dark:bg-dark-bg rounded-sm overflow-hidden">
              <span
                className={`block h-full rounded-sm ${
                  index === 0 ? 'bg-[#F2D45C]' : 'bg-slate-300 dark:bg-slate-600'
                }`}
                style={{ width: `${Math.max((row[shape.measure] / max) * 100, 1)}%` }}
              />
            </span>
            <span className="w-20 shrink-0 text-right tabular-nums text-slate-600 dark:text-slate-400">
              {formatNumber(row[shape.measure])}
            </span>
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <p className="mt-2 text-xs text-slate-500">and {hidden.toLocaleString()} more</p>
      )}
    </div>
  );
}

function Line({ resultData, shape }) {
  const key = shape.timeColumn;
  const points = resultData.filter((row) => typeof row[shape.measure] === 'number');
  if (points.length < 2) return <Bars rows={points} shape={shape} hidden={0} />;

  const values = points.map((row) => row[shape.measure]);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const peak = points.findIndex((row) => row[shape.measure] === max);

  const W = 600;
  const H = 120;
  const x = (i) => (i / (points.length - 1)) * (W - 16) + 8;
  const y = (v) => H - 14 - ((v - min) / span) * (H - 32);
  const path = points.map((row, i) => `${i ? 'L' : 'M'}${x(i)},${y(row[shape.measure])}`).join(' ');

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-28" role="img"
        aria-label={`${shape.measure} over ${key}, highest ${formatNumber(max)}`}>
        <path d={path} fill="none" strokeWidth="2" className="stroke-slate-400 dark:stroke-slate-500" />
        <circle cx={x(peak)} cy={y(max)} r="4" fill="#F2D45C" />
        <text
          x={Math.min(Math.max(x(peak), 30), W - 30)}
          y={Math.max(y(max) - 9, 11)}
          textAnchor="middle"
          className="fill-slate-700 dark:fill-slate-200"
          fontSize="11"
        >
          {formatNumber(max)}
        </text>
      </svg>
      <div className="flex justify-between text-xs text-slate-500">
        <span>{String(points[0][key])}</span>
        <span>{String(points[points.length - 1][key])}</span>
      </div>
    </div>
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
  const [showTable, setShowTable] = useState(false);
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
            <Line resultData={resultData} shape={shape} />
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
