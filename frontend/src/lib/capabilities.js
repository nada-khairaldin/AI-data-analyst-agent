import { classifyColumns } from './suggestions.js';

/**
 * What the app can and cannot do, derived from the planner's own vocabulary
 * so the UI can never promise more than the agent will attempt.
 *
 * From backend/app/agent/schemas.py:
 *   AGGREGATION_OPERATIONS = sum, mean, count, min, max
 *   TOOL_SCHEMAS            = filter_data, aggregate_data (group_by),
 *                             sort_data, limit_results, select_columns
 *
 * Nothing in that list creates a column, fits a model, or computes a
 * statistic over two columns, which is exactly what the "not yet" list says.
 */

export const CAN_ASK_LINE =
  'You can ask about: totals, averages, counts, highest and lowest, filters, '
  + 'grouping by category or month, top results.';

export const NOT_YET_LINE =
  'Not yet: predictions, calculations between columns, statistics such as '
  + 'correlation.';

export const NOT_YET = [
  'Predictions or forecasts',
  'Calculations between columns, such as profit from revenue minus cost',
  'Statistics such as correlation or significance tests',
];

/**
 * One example per capability, written from this dataset's own columns with
 * the same templates as the starter questions. A capability with no column
 * to demonstrate it is left out rather than shown with a made-up name.
 *
 * @returns {Array<{ capability: string, example: string }>}
 */
export function capabilityExamples(columns) {
  const { numbers, texts, dates, measures, groups, averageable } =
    classifyColumns(columns);

  const measure = measures[0];
  const group = groups[0];
  const date = dates[0];
  const items = [];

  // aggregate_data, operation: sum
  if (measure) {
    items.push({
      capability: 'Totals',
      example: `What is the total ${measure.name}?`,
    });
  }
  // aggregate_data, operation: mean
  if (averageable) {
    items.push({
      capability: 'Averages',
      example: `What is the average ${averageable.name}?`,
    });
  }
  // aggregate_data, operation: count
  if (group) {
    items.push({
      capability: 'Counts',
      example: `How many rows are there for each ${group.name}?`,
    });
  }
  // aggregate_data + sort_data + limit_results
  if (group && measure) {
    items.push({
      capability: 'Highest and lowest',
      example: `Which ${group.name} has the highest total ${measure.name}?`,
    });
  }
  // filter_data
  if (group && measure) {
    items.push({
      capability: 'Filters',
      // The trailing gap is deliberate: clicking an example fills the box
      // rather than sending it, and a filter needs a value only the user
      // knows. Inventing one would send a question about a row that may not
      // exist.
      example: `Total ${measure.name} where ${group.name} is …`,
    });
  }
  // aggregate_data with group_by on the derived _month column
  if (date && measure) {
    items.push({
      capability: 'Grouping by month',
      example: `Show total ${measure.name} per month`,
    });
  }
  // limit_results
  if (group && measure) {
    items.push({
      capability: 'Top results',
      // Not "top 5 Product": column names are singular in most datasets and
      // the phrase has to read properly whatever the column is called.
      example: `Show the top 5 by total ${measure.name}, grouped by ${group.name}`,
    });
  }
  // A dataset with no numeric column at all still gets something true.
  if (items.length === 0 && texts.length) {
    items.push({
      capability: 'Counts',
      example: `How many rows are there for each ${texts[0].name}?`,
    });
  }
  // Keeps the popover a glance rather than a manual.
  return items.slice(0, 7);
}

/**
 * The nearest questions the app can actually answer, offered under a
 * cannot_answer reply. Built from the same templates, so a suggestion is
 * never one the planner would also refuse. No LLM call.
 */
export function closestAnswerable(columns, limit = 2) {
  const { measures, groups, dates, averageable } = classifyColumns(columns);
  const measure = measures[0];
  const group = groups[0];
  const out = [];

  if (group && measure) out.push(`Which ${group.name} has the highest total ${measure.name}?`);
  if (averageable) out.push(`What is the average ${averageable.name}?`);
  if (dates[0] && measure) out.push(`Show total ${measure.name} per month`);
  if (group) out.push(`How many rows are there for each ${group.name}?`);

  return out.slice(0, limit);
}
