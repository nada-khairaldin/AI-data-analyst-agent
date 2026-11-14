import React, { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { capabilityExamples, NOT_YET } from '../lib/capabilities';

/**
 * The capability list, written from this dataset's own columns.
 *
 * A popover beside the input rather than a modal or a tour: it answers a
 * question the user has while they are typing, and it costs nothing to
 * ignore. Clicking an example fills the box instead of sending it, so a
 * template with a value to supply ("… where Country is …") is usable.
 */
export default function WhatCanIAsk({ columns, onPick }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const items = capabilityExamples(columns);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => event.key === 'Escape' && setOpen(false);
    const onClick = (event) => {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 underline underline-offset-2"
      >
        What can I ask?
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="What can I ask?"
          className="absolute bottom-full mb-2 right-0 w-[min(22rem,calc(100vw-2rem))] max-h-[60vh] overflow-y-auto bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl shadow-lg p-4 z-20"
        >
          <div className="flex items-start justify-between gap-3 mb-2">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              What can I ask?
            </h3>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close"
              className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            >
              <X size={15} />
            </button>
          </div>

          {items.length > 0 ? (
            <ul className="divide-y divide-slate-100 dark:divide-dark-border">
              {items.map((item) => (
                <li key={item.capability} className="py-2">
                  <div className="text-xs text-slate-500">{item.capability}</div>
                  <button
                    type="button"
                    dir="auto"
                    onClick={() => {
                      onPick?.(item.example);
                      setOpen(false);
                    }}
                    className="mt-0.5 text-left text-sm text-slate-800 dark:text-slate-200 hover:text-primary"
                  >
                    {item.example}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">
              This dataset has no columns the analysis can work with.
            </p>
          )}

          <div className="mt-3 pt-3 border-t border-slate-200 dark:border-dark-border">
            <div className="text-xs text-slate-500 mb-1">Not yet</div>
            <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-0.5">
              {NOT_YET.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
