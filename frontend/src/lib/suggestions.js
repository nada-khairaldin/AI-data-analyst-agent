// Three starter questions built from the dataset's own columns, with fixed
// templates and no LLM: a suggestion is only worth showing if it is certain
// to run, and a free-tier call spent before the user has asked anything is a
// call they cannot spend on a real question.

const NUMERIC = /^(u?int|float|Int|Float|decimal|number)/;
const TEXT = /^(str|string|object|category)/;
const DATE = /^(datetime|date|timestamp)/;

// Columns the upload derives for "per month" questions. They are useful to
// the planner and noise in a suggestion.
const DERIVED = /_(year|month)$/;

// An identifier averages to nothing and groups into as many buckets as there
// are rows. The camelCase boundary matters: CustomerID and OrderID are ids,
// Madrid is not.
const ID_LIKE = /(^id$|_id$|[a-z]Id$|ID$|_code$|^code$)/;

// Only some numbers are meaningful in a total. Revenue summed is revenue;
// Price summed is nothing at all, and Age summed is nonsense -- which is
// exactly what "Show total Age per month" was before this split.
const TOTALLABLE = /(revenue|sales|amount|total|quantity|qty|count|spend|spent|units)/i;

// Grouping by a free-text column gives one bucket per row.
const FREE_TEXT = /(name|title|description|comment|note|email|phone|address)/i;

const kind = (dtype = '') => {
  if (DATE.test(dtype)) return 'date';
  if (NUMERIC.test(dtype)) return 'number';
  if (TEXT.test(dtype)) return 'text';
  return 'other';
};

/**
 * @param {Array<{name, dtype, available}>} columns from the columns endpoint
 * @returns {string[]} up to three questions, fewer if the columns cannot
 *   support them. Never throws and never invents a column name.
 */
export function suggestQuestions(columns) {
  if (!Array.isArray(columns)) return [];

  const usable = columns.filter(
    (column) => column?.available && column.name && !DERIVED.test(column.name),
  );
  const present = new Set(columns.filter((c) => c?.available).map((c) => c.name));

  const numbers = usable.filter((c) => kind(c.dtype) === 'number' && !ID_LIKE.test(c.name));
  const texts = usable.filter((c) => kind(c.dtype) === 'text' && !ID_LIKE.test(c.name));
  // "per month" only works where the upload actually derived the companion.
  const dates = usable.filter(
    (c) => kind(c.dtype) === 'date' && present.has(`${c.name}_month`),
  );

  // Totals need a totallable number; falling back to any number keeps a
  // suggestion on screen for a dataset that has none.
  const totallable = numbers.filter((c) => TOTALLABLE.test(c.name));
  const measures = totallable.length ? totallable : numbers;

  // Prefer a low-cardinality label (Country, Segment) over a per-row one.
  const groups = [...texts].sort(
    (a, b) => Number(FREE_TEXT.test(a.name)) - Number(FREE_TEXT.test(b.name)),
  );

  // The average is more interesting on a number the totals did not already
  // use -- Price next to total quantity, Age next to total spend.
  const averageable = numbers.find((c) => c.name !== measures[0]?.name) || numbers[0];

  const questions = [];

  if (groups.length && measures.length) {
    questions.push(`Which ${groups[0].name} has the highest total ${measures[0].name}?`);
  }
  if (averageable) {
    questions.push(`What is the average ${averageable.name}?`);
  }
  if (dates.length && measures.length) {
    questions.push(`Show total ${(measures[1] || measures[0]).name} per month`);
  }

  // A dataset with no numeric column at all still deserves a starting point.
  if (questions.length === 0 && texts.length) {
    questions.push(`How many rows are there for each ${texts[0].name}?`);
  }

  return questions.slice(0, 3);
}
