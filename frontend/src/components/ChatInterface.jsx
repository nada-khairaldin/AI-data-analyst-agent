import React, { useState, useRef, useEffect } from 'react';
import { Send, User, ChevronDown, CheckCircle2, ChevronRight, BarChart2 } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer
} from 'recharts';

export default function ChatInterface({ 
  dataset,
  conversation,
  onSendMessage
}) {
  const [input, setInput] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const messagesEndRef = useRef(null);

  const messages = conversation?.messages || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAnalyzing]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isAnalyzing) return;
    
    onSendMessage(input.trim());
    setInput('');
    setIsAnalyzing(true);
    
    // Mock simulation of API response
    setTimeout(() => {
      setIsAnalyzing(false);
    }, 2000);
  };

  if (!dataset || !conversation) return null;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 dark:bg-dark-bg">
      {/* Header */}
      <header className="bg-white/80 dark:bg-dark-sidebar/80 backdrop-blur-md border-b border-slate-200 dark:border-dark-border px-6 py-4 flex items-center shrink-0 min-h-[72px]">
        <h2 className="text-sm font-medium text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <span className="text-slate-500 font-normal">{dataset.name}</span>
          <span className="text-slate-400">/</span>
          {conversation.title}
        </h2>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4">
            <div className="w-16 h-16 bg-blue-100 dark:bg-primary/10 rounded-2xl flex items-center justify-center text-primary mb-2">
              <BarChart2 size={32} />
            </div>
            <h3 className="text-lg font-medium text-slate-800 dark:text-slate-200">Start your analysis</h3>
            <div className="flex flex-wrap justify-center gap-2 max-w-md">
              <button onClick={() => setInput('Show top 5 products')} className="px-3 py-1.5 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-full text-sm hover:border-primary/50 transition-colors">Show top 5 products</button>
              <button onClick={() => setInput('Which month had the highest sales?')} className="px-3 py-1.5 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-full text-sm hover:border-primary/50 transition-colors">Which month had the highest sales?</button>
              <button onClick={() => setInput('What is the average price per product?')} className="px-3 py-1.5 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-full text-sm hover:border-primary/50 transition-colors">What is the average price per product?</button>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'agent' && (
              <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center flex-shrink-0 mt-1">
                <BarChart2 size={16} />
              </div>
            )}
            
            <div className={`max-w-[85%] ${msg.role === 'user' ? 'bg-slate-200/50 dark:bg-white/10 text-slate-800 dark:text-white px-4 py-3 rounded-2xl rounded-tr-sm' : 'space-y-4'}`}>
              
              {/* Agent Text Response */}
              {msg.role === 'agent' && (
                <div className="text-slate-800 dark:text-slate-200 text-[15px] leading-relaxed">
                  {msg.content}
                </div>
              )}

              {/* User Text Response */}
              {msg.role === 'user' && (
                <div className="text-[15px]">
                  {msg.content}
                </div>
              )}

              {/* Chart / Data Result (Agent only) */}
              {msg.role === 'agent' && msg.resultData && (
                <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 shadow-sm">
                  
                  <div className="flex flex-col md:flex-row gap-8">
                    {/* Data Table */}
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">{msg.chartTitle || 'Results'}</h4>
                      <div className="overflow-hidden border border-slate-100 dark:border-dark-border rounded-lg">
                        <table className="w-full text-sm text-left">
                          <thead className="bg-slate-50 dark:bg-dark-bg text-slate-500">
                            <tr>
                              <th className="px-3 py-2 font-medium">Product</th>
                              <th className="px-3 py-2 font-medium text-right">Total Quantity Sold</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
                            {msg.resultData.map((row, i) => (
                              <tr key={i} className="hover:bg-slate-50 dark:hover:bg-dark-elevated transition-colors">
                                <td className="px-3 py-2 text-slate-700 dark:text-slate-300 font-medium">{row.product}</td>
                                <td className="px-3 py-2 text-right text-slate-600 dark:text-slate-400">{row.quantity?.toLocaleString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Chart (if applicable) */}
                    {msg.showChart && (
                      <div className="flex-1 h-64 border-l border-slate-100 dark:border-dark-border pl-0 md:pl-8">
                        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">Total Quantity Sold by Product</h4>
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={msg.resultData} layout="vertical" margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#334155" opacity={0.3} />
                            <XAxis type="number" hide />
                            <YAxis dataKey="product" type="category" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 12}} width={80} />
                            <RechartsTooltip cursor={{fill: 'transparent'}} contentStyle={{backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#f1f5f9'}} />
                            <Bar dataKey="quantity" fill="#38BDF8" radius={[0, 4, 4, 0]} barSize={20} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Analysis Plan Expandable (Agent only) */}
              {msg.role === 'agent' && msg.plan && (
                <details className="group bg-slate-50 dark:bg-dark-elevated border border-slate-200 dark:border-dark-border rounded-lg overflow-hidden transition-all max-w-2xl">
                  <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-dark-card transition-colors">
                    <ChevronRight size={16} className="text-slate-400 group-open:rotate-90 transition-transform" />
                    <span className="flex items-center gap-2">
                      <BarChart2 size={16} className="text-primary" />
                      Analysis performed <span className="text-slate-400 font-normal text-xs ml-1">(click to expand)</span>
                    </span>
                  </summary>
                  <div className="px-5 py-4 border-t border-slate-200 dark:border-dark-border bg-white dark:bg-dark-card space-y-4 text-sm">
                    
                    <div>
                      <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Question</h5>
                      <p className="text-slate-600 dark:text-slate-400">{msg.plan.question}</p>
                    </div>

                    <div>
                      <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-2">Analysis Steps</h5>
                      <ol className="list-decimal pl-5 space-y-1 text-slate-600 dark:text-slate-400">
                        {msg.plan.steps?.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Data Used</h5>
                        <p className="text-slate-600 dark:text-slate-400">{msg.plan.columnsUsed?.join(', ')}</p>
                      </div>
                      <div>
                        <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Filters</h5>
                        <p className="text-slate-600 dark:text-slate-400">{msg.plan.filters || 'None'}</p>
                      </div>
                    </div>
                    
                    <div className="pt-2 flex items-center gap-1.5 text-success font-medium text-xs bg-success/10 w-fit px-2 py-1 rounded-full">
                      <CheckCircle2 size={14} />
                      Plan validated
                    </div>
                  </div>
                </details>
              )}
            </div>
          </div>
        ))}
        
        {isAnalyzing && (
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center flex-shrink-0 mt-1 border border-primary/30">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
            </div>
            <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border px-4 py-3 rounded-2xl rounded-tl-sm text-sm text-slate-500 flex flex-col gap-2 shadow-sm min-w-[200px]">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-success" />
                <span className="text-slate-700 dark:text-slate-300">Understanding question</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-success" />
                <span className="text-slate-700 dark:text-slate-300">Building analysis plan</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded-full border-[1.5px] border-primary border-t-transparent animate-spin ml-0.5 mr-[1px]"></div>
                <span className="text-primary font-medium">Running analysis</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 md:p-6 bg-white dark:bg-dark-sidebar border-t border-slate-200 dark:border-dark-border">
        <form onSubmit={handleSend} className="max-w-4xl mx-auto relative flex items-center">
          <input 
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={isAnalyzing}
            placeholder="Ask another question about your data..."
            className="w-full bg-slate-100 dark:bg-dark-bg border border-slate-200 dark:border-dark-border text-slate-800 dark:text-white rounded-full py-3.5 pl-6 pr-14 focus:outline-none focus:border-primary/50 transition-colors shadow-sm disabled:opacity-50"
          />
          <button 
            type="submit"
            disabled={!input.trim() || isAnalyzing}
            className="absolute right-2 top-1.5 bottom-1.5 w-10 h-10 bg-primary hover:bg-primary/90 text-white rounded-full flex items-center justify-center transition-transform active:scale-95 disabled:opacity-50 disabled:active:scale-100"
          >
            <Send size={18} className="ml-1" />
          </button>
        </form>
      </div>
    </div>
  );
}
