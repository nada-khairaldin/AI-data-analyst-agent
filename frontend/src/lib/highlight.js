// Finds the figure in an answer that the result actually supports, so the
// marker lands on a number the analysis produced rather than on whatever
// digits happen to appear first. If nothing matches, nothing is highlighted:
// a highlight on the wrong number is worse than none.

// The same value can be written several ways in a sentence -- 2709, 2,709,
// 2709.0 -- and JSON has already turned 2709.0 into the number 2709.
function numberForms(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return [];
  const forms = [
    String(value),
    value.toLocaleString('en-US'),
    value.toFixed(1),
    value.toFixed(2),
    value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
    value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  ];
  return forms.filter((form) => form.length > 0);
}

// "2709" must not match inside "27091" or "2709.5". A trailing "." or ","
// only continues the number when a digit follows it -- otherwise it is the
// end of the sentence, which is where a figure most often sits.
function indexOfStandalone(text, needle) {
  const digitBefore = (at) => at >= 0 && /[\d.,]/.test(text[at] ?? '');
  const continuesAfter = (at) => {
    const ch = text[at];
    if (ch === undefined) return false;
    if (/\d/.test(ch)) return true;
    if (ch === '.' || ch === ',') return /\d/.test(text[at + 1] ?? '');
    return false;
  };

  let from = 0;
  for (;;) {
    const at = text.indexOf(needle, from);
    if (at === -1) return -1;
    if (!digitBefore(at - 1) && !continuesAfter(at + needle.length)) return at;
    from = at + 1;
  }
}

/**
 * @returns {{before: string, figure: string, after: string} | null}
 */
export function splitOnFigure(text, resultData) {
  if (typeof text !== 'string' || !text) return null;
  if (!Array.isArray(resultData) || resultData.length === 0) return null;

  // Every row, not just the first: a grouped result is often ordered by its
  // key, so the headline figure the sentence leads with can be any row.
  const numbers = resultData
    .slice(0, 50)
    .flatMap((row) => Object.values(row ?? {}))
    .filter((value) => typeof value === 'number' && Number.isFinite(value));
  if (numbers.length === 0) return null;

  const forms = [...new Set(numbers.flatMap(numberForms))];

  // Earliest in the sentence wins -- that is the figure being reported, not
  // one of the also-rans. Longest breaks a tie so "2,709.0" beats "2".
  let best = null;
  for (const form of forms) {
    const at = indexOfStandalone(text, form);
    if (at === -1) continue;
    if (!best || at < best.at || (at === best.at && form.length > best.form.length)) {
      best = { at, form };
    }
  }
  if (!best) return null;

  return {
    before: text.slice(0, best.at),
    figure: best.form,
    after: text.slice(best.at + best.form.length),
  };
}
