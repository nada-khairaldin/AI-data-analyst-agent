import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

// Any failure has to be visible. The alternative — a spinner that never
// resolves — is the worst outcome, because it looks like progress.
export default function ErrorBanner({ message, onDismiss }) {
  if (!message) return null;
  return (
    <div className="shrink-0 flex items-start gap-3 px-6 py-3 bg-error/10 border-b border-error/30 text-sm">
      <AlertTriangle size={18} className="text-error shrink-0 mt-0.5" />
      <div className="flex-1 text-slate-700 dark:text-slate-200">{message}</div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 shrink-0"
          aria-label="Dismiss"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}
