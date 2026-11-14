import React, { useState } from 'react';
import { Download } from 'lucide-react';
import Logo from './Logo';

// Served from public/, so the path is the URL. Kept deliberately plain: a
// visual pass comes later and card styling would only be thrown away.
const SAMPLES = [
  {
    file: 'orders.csv',
    name: 'Sales orders',
    description: '1,500 orders, 2023-2024',
  },
  {
    file: 'customers.csv',
    name: 'Customers',
    description: 'Customer profiles and spending',
  },
  {
    file: 'bad.csv',
    name: 'Messy data',
    description: 'See how poor-quality data is rejected',
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
    <div className="text-left">
      <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">
        Or try a sample dataset
      </h3>

      <ul className="divide-y divide-slate-200 dark:divide-dark-border border-y border-slate-200 dark:border-dark-border">
        {SAMPLES.map((sample) => {
          const isThisOne = loadingFile === sample.file;
          return (
            <li
              key={sample.file}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3"
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-800 dark:text-slate-200">
                  {sample.name}
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-400">
                  {sample.description}
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => tryIt(sample)}
                  disabled={busy}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
                >
                  {isThisOne && <Logo size={14} variant="loading" />}
                  {isThisOne ? 'Loading…' : 'Try it'}
                </button>

                {sample.downloadable !== false && (
                  <a
                    href={url(sample.file)}
                    download={sample.file}
                    className="inline-flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  >
                    <Download size={14} />
                    Download
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {error && (
        <p className="mt-3 text-sm text-rose-700 dark:text-error">{error}</p>
      )}
    </div>
  );
}
