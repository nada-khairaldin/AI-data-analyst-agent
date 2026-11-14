import React from 'react';
import AnswerCard from './AnswerCard';

/**
 * One worked example, shown before anything is uploaded.
 *
 * It renders through AnswerCard, the same component every real answer uses,
 * with static rows in place of a result. That is the whole point: the
 * example cannot promise a layout the chat no longer has, because there is
 * only one layout. No API call and no LLM.
 */

// Illustrative figures for the example, not a computed result.
const RESULT = [
  { Country: 'Germany', revenue: 617940 },
  { Country: 'France', revenue: 441300 },
  { Country: 'Spain', revenue: 352100 },
];

const PLAN = { steps: ['Group by Country', 'Calculate SUM of revenue'] };

const SENTENCE = 'Germany, with 617,940 in revenue.';

export default function ExampleAnswer() {
  return (
    <div>
      <p className="text-sm text-slate-500 mb-3">For example</p>

      <div className="flex justify-end">
        <p
          dir="auto"
          className="max-w-[85%] bg-slate-200/60 dark:bg-white/10 text-slate-800 dark:text-white px-3.5 py-2 rounded-2xl rounded-tr-sm text-sm"
        >
          Which country had the highest revenue in 2024?
        </p>
      </div>

      <div className="mt-3">
        <AnswerCard text={SENTENCE} resultData={RESULT} resultKind="table" plan={PLAN} />
      </div>
    </div>
  );
}
