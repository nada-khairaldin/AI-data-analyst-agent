import React from 'react';
import { X } from 'lucide-react';

// Any failure has to be visible. The alternative — a spinner that never
// resolves — is the worst outcome, because it looks like progress.
export default function ErrorBanner({ message, onRetry, onDismiss }) {
  if (!message) return null;
  return (
    <div className="shrink-0 flex items-start gap-4 px-6 py-3 border-b border-rule bg-surface text-sm">
      <p className="flex-1 text-ink">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 text-verdigris hover:underline"
        >
          Retry
        </button>
      )}
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-graphite hover:text-ink shrink-0"
          aria-label="Dismiss"
        >
          <X size={15} strokeWidth={1.5} />
        </button>
      )}
    </div>
  );
}
