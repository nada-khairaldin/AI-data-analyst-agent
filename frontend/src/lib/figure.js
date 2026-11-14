// Finding the figure that answers the question inside the sentence that
// reports it, so the marker lands on a number the result actually contains
// and never on a year or a row count that happens to look similar.

// The same value can be written several ways in a sentence -- 2709, 2,709,
// 2709.0 -- and JSON has already turned 2709.0 into the number 2709.
function formsOf(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return [];
  const forms = [
    String(value),
    value.toLocaleString('en-US'),
    value.toFixed(0),
    value.toFixed(1),
    value.toFixed(2),
    value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
    value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    Math.round(value).toLocaleString('en-US'),
  ];
  return [...new Set(forms)].filter(Boolean);
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
 * @param {string} text the full sentence
 * @param {number} value the figure the result says is the answer
 * @returns {{before: string, figure: string, after: string} | null}
 *   null when the sentence does not contain it: a marker on the wrong
 *   number is worse than no marker.
 */
export function splitOnValue(text, value) {
  if (typeof text !== 'string' || !text) return null;

  // Longest first, so "2,709.00" wins over the "2" inside it.
  const forms = formsOf(value).sort((a, b) => b.length - a.length);
  for (const form of forms) {
    const at = indexOfStandalone(text, form);
    if (at !== -1) {
      return { before: text.slice(0, at), figure: form, after: text.slice(at + form.length) };
    }
  }
  return null;
}

export function formatNumber(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value ?? '—');
  // Whole numbers keep no decimals; fractions keep at most two.
  return Number.isInteger(value)
    ? value.toLocaleString('en-US')
    : value.toLocaleString('en-US', { maximumFractionDigits: 2 });
}
