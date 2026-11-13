import React, { useEffect, useRef } from 'react';

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
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-ink/40"
      onClick={onCancel}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md bg-surface rounded-md border border-rule overflow-hidden"
      >
        <div className="p-6">
          <h3 className="text-ink">{title}</h3>
          <div className="text-sm text-graphite mt-1.5 leading-relaxed">{body}</div>
        </div>

        <div className="px-6 py-4 border-t border-rule flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isBusy}
            className="px-4 py-2 text-sm rounded-md text-ink border border-rule hover:border-graphite disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            disabled={isBusy}
            className="px-4 py-2 text-sm rounded-md text-paper bg-ink hover:brightness-125 disabled:opacity-60"
          >
            {isBusy ? 'Deleting' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
