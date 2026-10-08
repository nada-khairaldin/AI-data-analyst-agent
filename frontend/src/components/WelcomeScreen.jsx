import React from 'react';
import { UploadCloud, ShieldCheck, Lock, BarChart2 } from 'lucide-react';

export default function WelcomeScreen({ onFileUpload, isUploading }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 h-full bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary overflow-hidden">
      <div className="max-w-2xl w-full text-center space-y-6">
        
        <div className="space-y-4">
          <div className="w-14 h-14 bg-blue-100 dark:bg-primary/20 text-blue-600 dark:text-primary rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm">
            <BarChart2 size={28} />
          </div>
          <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
            Analyze your data with AI
          </h2>
          <p className="text-slate-600 dark:text-slate-400 max-w-lg mx-auto text-lg leading-relaxed">
            Upload a CSV file, ask questions in natural language, and get clear answers with charts and insights.
          </p>
        </div>

        <div className="max-w-xl mx-auto">
          <label className={`
            block relative border-2 border-dashed rounded-3xl p-8 md:p-10 transition-all cursor-pointer
            ${isUploading 
              ? 'border-primary bg-primary/5 dark:bg-primary/10' 
              : 'border-slate-300 dark:border-dark-border bg-white dark:bg-dark-card hover:border-primary/50 hover:bg-slate-50 dark:hover:bg-dark-elevated shadow-sm'
            }
          `}>
            <input 
              type="file" 
              className="hidden" 
              accept=".csv" 
              onChange={onFileUpload}
              disabled={isUploading}
            />
            
            <div className="flex flex-col items-center justify-center text-center space-y-4">
              <div className="p-4 bg-slate-100 dark:bg-dark-bg rounded-full">
                <UploadCloud size={32} className={isUploading ? 'text-primary animate-bounce' : 'text-slate-500 dark:text-slate-400'} />
              </div>
              <div>
                <p className="text-lg font-semibold text-slate-700 dark:text-slate-200">
                  {isUploading ? 'Uploading...' : 'Drag & drop your CSV file here'}
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                  or click to browse
                </p>
              </div>
              <p className="text-xs font-medium text-slate-400 bg-slate-100 dark:bg-dark-bg px-3 py-1 rounded-full">
                .csv files only
              </p>
            </div>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6 max-w-3xl mx-auto border-t border-slate-200 dark:border-dark-border">
          <div className="flex flex-col items-center text-center space-y-1.5">
            <div className="text-slate-400 dark:text-slate-500">
              <Lock size={20} />
            </div>
            <h3 className="font-semibold text-slate-700 dark:text-slate-300">No coding required</h3>
            <p className="text-sm text-slate-500 dark:text-slate-500">Just ask your question</p>
          </div>
          <div className="flex flex-col items-center text-center space-y-1.5">
            <div className="text-slate-400 dark:text-slate-500">
              <BarChart2 size={20} />
            </div>
            <h3 className="font-semibold text-slate-700 dark:text-slate-300">Clear & visual results</h3>
            <p className="text-sm text-slate-500 dark:text-slate-500">Tables, charts and insights</p>
          </div>
          <div className="flex flex-col items-center text-center space-y-1.5">
            <div className="text-slate-400 dark:text-slate-500">
              <ShieldCheck size={20} />
            </div>
            <h3 className="font-semibold text-slate-700 dark:text-slate-300">Full transparency</h3>
            <p className="text-sm text-slate-500 dark:text-slate-500">See the analysis plan</p>
          </div>
        </div>

      </div>
    </div>
  );
}
