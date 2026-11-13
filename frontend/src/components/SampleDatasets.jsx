import React, { useState } from 'react';

// Served from public/, so the path is the URL.
const SAMPLES = [
  {
    file: 'orders.csv',
    name: 'Sales orders',
    rows: '1,500 rows',
    period: '2023–2024',
  },
  {
    file: 'customers.csv',
    name: 'Customers',
    rows: '15 rows',
    period: 'profiles and spending',
  },
  {
    file: 'bad.csv',
    name: 'Messy data',
    rows: '20 rows',
    period: 'rejected on upload',
    // Downloading a file whose whole purpose is to be refused is not useful.
    downloadable: false,
  },
];

const url = (file) => `${import.meta.env.BASE_URL}samples/${file}`;

export default function SampleDatasets({ onFileUpload, isUploading }) {
  const [loadingFile, setLoadingFile] = useState(null);
  const [error, setError] = useState(null);

  // Fetch it, wrap it as a File, and hand it to the same upload function the
  // picker and the drop zone use -- so the loading state, the error banner
  // and the rejection screen are all the real ones, not a second code path
  // that can drift from them.
  const tryIt = async (sample) => {
    setError(null);
    setLoadingFile(sample.file);
    try {
      const response = await fetch(url(sample.file));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      await onFileUpload(new File([blob], sample.file, { type: 'text/csv' }));
    } catch {
      setError(`Could not load ${sample.file}. Check your connection and try again.`);
    } finally {
      setLoadingFile(null);
    }
  };

  const busy = isUploading || loadingFile !== null;

  return (
    <div>
      <h3 className="text-ink">Or try a sample</h3>

      <ul className="mt-3 border-t border-rule">
        {SAMPLES.map((sample) => {
          const isThisOne = loadingFile === sample.file;
          return (
            <li
              key={sample.file}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-2.5 border-b border-rule"
            >
              <span className="text-ink">{sample.name}</span>
              <span className="text-sm text-graphite tabular">
                {sample.rows} · {sample.period}
              </span>

              <span className="ml-auto flex items-baseline gap-4 shrink-0">
                <button
                  type="button"
                  onClick={() => tryIt(sample)}
                  disabled={busy}
                  className="text-sm text-verdigris hover:underline disabled:opacity-40 disabled:no-underline"
                >
                  {isThisOne ? 'Loading' : 'Try it'}
                </button>

                {sample.downloadable !== false && (
                  <a
                    href={url(sample.file)}
                    download={sample.file}
                    className="text-sm text-graphite hover:text-ink"
                  >
                    Download
                  </a>
                )}
              </span>
            </li>
          );
        })}
      </ul>

      {error && <p className="mt-3 text-sm text-ink border-l-2 border-rule pl-3">{error}</p>}
    </div>
  );
}
