// Reading a result's shape, so one card can render every answer the agent
// produces without being told which question was asked.

export const MAX_BARS = 12;

// The upload derives these so "per month" works on any CSV.
const TIME_COLUMN = /_month$|_year$/;
const ISO_DATE = /^\d{4}-\d{2}(-\d{2})?/;

const isNumber = (value) => typeof value === 'number' && Number.isFinite(value);

/**
 * Splits a result's columns into the ones that name a row and the one that
 * measures it. A grouped result can name a row with several columns at once
 * -- Country AND Product -- and labelling such a bar with only one of them
 * puts four "Germany" bars on the chart with no way to tell them apart.
 */
export function readShape(resultData, resultKind) {
  if (resultKind === 'scalar' || !Array.isArray(resultData)) {
    return { kind: 'scalar', value: resultData };
  }
  if (resultData.length === 0) return { kind: 'empty' };

  // Union of keys in first-seen order, so a row missing one cannot drop a
  // column from the header.
  const columns = [];
  for (const row of resultData) {
    for (const key of Object.keys(row)) if (!columns.includes(key)) columns.push(key);
  }

  const numeric = columns.filter((key) => resultData.some((row) => isNumber(row[key])));
  const groupColumns = columns.filter((key) => !numeric.includes(key));
  // The measure is the last numeric column: a grouped aggregation puts the
  // keys first and the computed value last.
  const measure = numeric[numeric.length - 1] ?? null;

  if (!measure || groupColumns.length === 0) {
    return { kind: 'table', columns, groupColumns, measure };
  }

  const timeColumn = groupColumns.find(
    (key) => TIME_COLUMN.test(key) || resultData.every((row) => ISO_DATE.test(String(row[key] ?? ''))),
  );

  return {
    kind: timeColumn && groupColumns.length === 1 ? 'time' : 'category',
    columns,
    groupColumns,
    measure,
    timeColumn: timeColumn ?? null,
  };
}

/** "Germany, Docking Station" — every group column, never just the first. */
export function rowLabel(row, groupColumns) {
  return groupColumns
    .map((key) => (row[key] === null || row[key] === undefined ? '—' : String(row[key])))
    .join(', ');
}

/**
 * The bars to draw: the largest MAX_BARS by value, plus how many were left
 * out. Sorting by value rather than keeping the result's own order is what
 * makes "the first bar" mean "the biggest" on every chart.
 */
export function topRows(resultData, measure, limit = MAX_BARS) {
  const sorted = [...resultData].sort((a, b) => (b[measure] ?? -Infinity) - (a[measure] ?? -Infinity));
  return { rows: sorted.slice(0, limit), hidden: Math.max(0, sorted.length - limit) };
}

const OPERATION_WORDS = {
  SUM: 'Total',
  AVERAGE: 'Average',
  COUNT: 'Number of',
  MINIMUM: 'Lowest',
  MAXIMUM: 'Highest',
};

/**
 * "Total quantity by Country and Product".
 *
 * The server's own chartTitle names only chart_plan.x, which is one column,
 * so a result grouped by two columns was captioned as though it were
 * grouped by one. The operation comes from the plan's own step wording and
 * the grouping from the result itself, so the caption cannot disagree with
 * the chart beneath it.
 */
export function chartCaption(plan, shape) {
  if (!shape?.measure || !shape.groupColumns?.length) return null;

  let word = null;
  for (const step of plan?.steps || []) {
    const match = /^Calculate\s+(\w+)\s+of\s+/i.exec(String(step));
    if (match) word = OPERATION_WORDS[match[1].toUpperCase()] ?? null;
  }

  // "OrderDate_month" is the app's own column, not a word anyone asked
  // for: the caption says "month".
  const by = shape.groupColumns
    .map((name) => name.replace(/^.*_(month|year)$/, '$1'))
    .join(' and ');
  return word ? `${word} ${shape.measure} by ${by}` : `${shape.measure} by ${by}`;
}
