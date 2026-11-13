import React from 'react';
import { AlertTriangle, FileText, UploadCloud, X } from 'lucide-react';

// A rejection is stated in words and in the bar, not in a wash of red: the
// palette has no alarm colour, and the marker reads as "look here" without
// shouting.

function percent(value, fallback = 0) {
  const parsed = Number.parseFloat(String(value ?? '').replace('%', ''));
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function DatasetRejected({
  filename,
  fileSize,
  missingRate,
  maxAllowed = '40%',
  reasons = [],
  onUploadAnother,
  onClose,
}) {
  const actual = percent(missingRate);
  const limit = percent(maxAllowed, 40);
  // Keep the threshold caption inside the bar's width: at 0% or 100% a
  // centred label would hang off the edge and lose half its text.
  const captionLeft = Math.min(Math.max(limit, 12), 88);

  return (
    // `my-auto` rather than `justify-center`: centring a flex child that is
    // taller than its scroll container makes the TOP of it unreachable, so
    // the icon and the title were simply gone on a short window. Auto margins
    // centre only when there is room and collapse when there is not.
    <div className="flex-1 h-full overflow-y-auto bg-paper">
      <div className="min-h-full flex flex-col p-4 sm:p-6">
        <div className="max-w-lg w-full mx-auto my-auto bg-surface rounded-md border border-rule ">
          <div className="relative p-6 sm:p-7 flex flex-col items-center text-center border-b border-rule">
            {onClose && (
              // Inside the card, not floating over the page: as an overlay it
              // sat on top of the title on a narrow window.
              <button
                onClick={onClose}
                aria-label="Close"
                className="absolute top-3 right-3 p-2 rounded-lg text-graphite hover:text-ink hover:bg-paper transition-colors"
              >
                <X size={20} />
              </button>
            )}

            <div className="w-14 h-14 bg-marker text-[#1D2321] rounded-full flex items-center justify-center mb-5 mt-2">
              <AlertTriangle size={28} />
            </div>
            <h2 className="text-xl font-bold text-ink px-6">
              This file can&apos;t be analysed
            </h2>
            <p className="text-sm text-graphite mt-2 max-w-sm">
              Too much of it is missing for any answer to be trustworthy, so it
              was not saved.
            </p>
          </div>

          <div className="p-5 sm:p-6 space-y-6">
            <div className="flex items-start gap-3 bg-paper border border-rule rounded-xl p-4">
              <FileText
                size={22}
                className="text-graphite shrink-0 mt-0.5"
              />
              <div className="min-w-0">
                {/* The whole name, wrapped. Truncating it hides exactly the
                    detail someone needs to know which file was refused. */}
                <div className="font-medium text-ink break-words">
                  {filename}
                </div>
                {fileSize && (
                  <div className="text-sm text-graphite mt-0.5">
                    {fileSize}
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="flex items-baseline justify-between gap-3 mb-3">
                <span className="text-sm font-medium text-ink">
                  Missing values
                </span>
                <span className="text-lg font-bold text-ink tabular">
                  {missingRate}
                </span>
              </div>

              {/* The bar is the whole point of this screen: it shows how far
                  past the limit the file is, not just that it failed. */}
              <div className="relative h-3 w-full bg-rule rounded-full overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 bg-ink rounded-full"
                  style={{ width: `${Math.min(Math.max(actual, 0), 100)}%` }}
                />
                <div
                  className="absolute inset-y-0 w-0.5 bg-ink"
                  style={{ left: `${Math.min(Math.max(limit, 0), 100)}%` }}
                />
              </div>

              <div className="relative mt-2 h-9 text-xs text-graphite">
                <span className="absolute left-0 top-0">0%</span>
                <span className="absolute right-0 top-0">100%</span>
                <span
                  className="absolute top-0 -translate-x-1/2 whitespace-nowrap font-medium text-ink"
                  style={{ left: `${captionLeft}%` }}
                >
                  limit {maxAllowed}
                </span>
              </div>
            </div>

            {reasons.length > 0 && (
              <ul className="space-y-2">
                {reasons.map((reason) => (
                  <li
                    key={reason}
                    className="flex items-start gap-2.5 text-sm border border-rule rounded-lg p-3 text-ink"
                  >
                    <AlertTriangle
                      size={15}
                      className="mt-0.5 shrink-0 text-ink"
                    />
                    <span className="break-words min-w-0">{reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="px-5 sm:px-6 py-5 bg-paper border-t border-rule flex justify-center rounded-b-2xl">
            <button
              onClick={onUploadAnother}
              className="flex items-center gap-2 px-6 py-2.5 bg-verdigris hover:brightness-110 text-paper rounded-lg font-semibold transition-all shadow-sm"
            >
              <UploadCloud size={18} />
              Upload another file
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
