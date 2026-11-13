import React, { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * window.confirm blocks the whole tab, cannot be styled, and in some browsers
 * is suppressed entirely — a delete that silently never happens is worse than
 * no delete at all.
 */
export default function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = 'Delete',
  isBusy = false,
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    confirmRef.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') onCancel?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50"
      onClick={onCancel}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border shadow-xl overflow-hidden"
      >
        <div className="p-6 flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-rose-100 dark:bg-error/15 text-rose-600 dark:text-error flex items-center justify-center shrink-0">
            <AlertTriangle size={20} />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-slate-900 dark:text-white">{title}</h3>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1.5 leading-relaxed">
              {body}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 bg-slate-50 dark:bg-dark-bg border-t border-slate-200 dark:border-dark-border flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isBusy}
            className="px-4 py-2 text-sm font-medium rounded-lg text-slate-700 dark:text-slate-300 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border hover:bg-slate-100 dark:hover:bg-dark-elevated transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            disabled={isBusy}
            className="px-4 py-2 text-sm font-semibold rounded-lg text-white bg-rose-600 hover:bg-rose-700 transition-colors disabled:opacity-60"
          >
            {isBusy ? 'Deleting…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
