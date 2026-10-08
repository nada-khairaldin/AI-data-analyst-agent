import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import DatasetOverview from './components/DatasetOverview';
import ChatInterface from './components/ChatInterface';
import PreprocessingReport from './components/PreprocessingReport';
import DatasetRejected from './components/DatasetRejected';
import { Menu, Sun, Moon } from 'lucide-react';

// Mock Data
const MOCK_DATASETS = [
  {
    id: '1',
    name: 'orders.csv',
    rowCount: 2384,
    colCount: 8,
    size: '45 KB',
    missingRate: '2.1%',
    duplicateRate: '0.4%',
    status: 'ready',
    conversations: [
      { id: 'c1', title: 'Product Performance', date: '2 hours ago', messageCount: 12,
        messages: [
          { role: 'user', content: 'Which product has the highest total quantity sold?' },
          { 
            role: 'agent', 
            content: 'The product with the highest total quantity sold is Laptop.\nTotal quantity sold: 1,248 units.',
            showChart: true,
            chartTitle: 'Top 5 products by total quantity',
            resultData: [
              { product: 'Laptop', quantity: 1248 },
              { product: 'Mouse', quantity: 986 },
              { product: 'Keyboard', quantity: 712 },
              { product: 'Monitor', quantity: 456 },
              { product: 'Headphones', quantity: 324 },
            ],
            plan: {
              question: 'Which product has the highest total quantity sold?',
              steps: [
                'Group by Product',
                'Calculate SUM of Quantity',
                'Sort by total quantity (descending)',
                'Take top 1 result'
              ],
              columnsUsed: ['Product', 'Quantity'],
              filters: 'None'
            }
          }
        ]
      },
      { id: 'c2', title: 'Sales Overview', date: '1 day ago', messageCount: 8, messages: [] },
      { id: 'c3', title: 'Revenue Analysis', date: '2 days ago', messageCount: 15, messages: [] }
    ]
  },
  {
    id: '2',
    name: 'customers.csv',
    rowCount: 1200,
    colCount: 6,
    size: '30 KB',
    status: 'ready',
    conversations: []
  },
  {
    id: '3',
    name: 'expenses.csv',
    rowCount: 856,
    colCount: 6,
    size: '22 KB',
    status: 'ready',
    conversations: []
  }
];

export default function App() {
  const [datasets, setDatasets] = useState(MOCK_DATASETS);
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [currentView, setCurrentView] = useState('welcome'); // welcome, overview, chat, report, rejected
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  // Theme state
  const [theme, setTheme] = useState('dark'); // 'light' or 'dark'

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    
    // Simulate upload delay and check
    setTimeout(() => {
      setIsUploading(false);
      
      // Simulate rejecting a file if its name includes 'problem' or 'bad'
      if (file.name.toLowerCase().includes('problem') || file.name.toLowerCase().includes('bad')) {
        setCurrentView('rejected');
      } else {
        // Success upload mock
        const newDataset = {
          id: Date.now().toString(),
          name: file.name,
          rowCount: Math.floor(Math.random() * 5000) + 100,
          colCount: Math.floor(Math.random() * 10) + 3,
          status: 'ready',
          conversations: []
        };
        setDatasets(prev => [newDataset, ...prev]);
        setActiveDatasetId(newDataset.id);
        setActiveConversationId(null);
        setCurrentView('overview');
      }
    }, 1500);
  };

  const handleSelectDataset = (id) => {
    setActiveDatasetId(id);
    setActiveConversationId(null);
    setCurrentView('overview');
    setIsMobileOpen(false);
  };

  const handleSelectConversation = (datasetId, conversationId) => {
    setActiveDatasetId(datasetId);
    setActiveConversationId(conversationId);
    setCurrentView('chat');
    setIsMobileOpen(false);
  };

  const handleNewConversation = (datasetId) => {
    const newConvId = 'conv_' + Date.now();
    const newConv = { id: newConvId, title: 'New Conversation', date: 'Just now', messageCount: 0, messages: [] };
    
    setDatasets(prev => prev.map(d => {
      if (d.id === datasetId) {
        return { ...d, conversations: [newConv, ...(d.conversations || [])] };
      }
      return d;
    }));
    
    setActiveDatasetId(datasetId);
    setActiveConversationId(newConvId);
    setCurrentView('chat');
    setIsMobileOpen(false);
  };

  const handleSendMessage = (text) => {
    setDatasets(prev => prev.map(d => {
      if (d.id === activeDatasetId) {
        return {
          ...d,
          conversations: d.conversations.map(c => {
            if (c.id === activeConversationId) {
              const newMessages = [...c.messages, { role: 'user', content: text }];
              // Update title if it's a new conversation
              const title = c.title === 'New Conversation' ? text.substring(0, 25) + '...' : c.title;
              return { ...c, title, messages: newMessages, messageCount: newMessages.length };
            }
            return c;
          })
        };
      }
      return d;
    }));
    
    // Simulate agent reply
    setTimeout(() => {
      setDatasets(prev => prev.map(d => {
        if (d.id === activeDatasetId) {
          return {
            ...d,
            conversations: d.conversations.map(c => {
              if (c.id === activeConversationId) {
                const reply = {
                  role: 'agent',
                  content: "I've analyzed the data for your request.",
                  showChart: false
                };
                return { ...c, messages: [...c.messages, reply], messageCount: c.messages.length + 1 };
              }
              return c;
            })
          };
        }
        return d;
      }));
    }, 2000);
  };

  const activeDataset = datasets.find(d => d.id === activeDatasetId);
  const activeConversation = activeDataset?.conversations?.find(c => c.id === activeConversationId);

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-dark-bg font-sans overflow-hidden">
      
      <Sidebar 
        datasets={datasets}
        activeDatasetId={activeDatasetId}
        activeConversationId={activeConversationId}
        onSelectDataset={handleSelectDataset}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onUploadDataset={() => setCurrentView('welcome')}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
      />

      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Mobile Header / Theme Toggle */}
        <div className="lg:hidden flex items-center justify-between p-4 bg-white dark:bg-dark-sidebar border-b border-slate-200 dark:border-dark-border z-10">
          <button 
            onClick={() => setIsMobileOpen(true)}
            className="p-2 -ml-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white"
          >
            <Menu size={24} />
          </button>
          <div className="font-semibold text-slate-800 dark:text-white">AI Data Analyst</div>
          <button 
            onClick={toggleTheme} 
            className="w-10 h-10 flex items-center justify-center -mr-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-colors"
          >
             {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
        
        {/* Desktop Theme Toggle (floating top right) */}
        <button 
          onClick={toggleTheme} 
          className="hidden lg:flex absolute top-4 right-6 z-50 w-10 h-10 items-center justify-center bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-full shadow-sm text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-colors"
          title="Toggle Theme"
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>

        {/* Main Content Area */}
        <main className="flex-1 overflow-hidden flex flex-col relative">
          {currentView === 'welcome' && (
            <WelcomeScreen 
              onFileUpload={handleFileUpload} 
              isUploading={isUploading} 
            />
          )}
          
          {currentView === 'overview' && activeDataset && (
            <DatasetOverview 
              dataset={activeDataset} 
              onBack={() => setCurrentView('welcome')}
              onNewConversation={handleNewConversation}
              onSelectConversation={handleSelectConversation}
              onShowReport={() => setCurrentView('report')}
            />
          )}
          
          {currentView === 'chat' && activeDataset && activeConversation && (
            <ChatInterface 
              dataset={activeDataset}
              conversation={activeConversation}
              onSendMessage={handleSendMessage}
            />
          )}
          
          {currentView === 'report' && activeDataset && (
            <PreprocessingReport 
              dataset={activeDataset}
              onBack={() => setCurrentView('overview')}
            />
          )}
          
          {currentView === 'rejected' && (
            <DatasetRejected 
              onUploadAnother={() => setCurrentView('welcome')}
              onClose={() => setCurrentView('welcome')}
            />
          )}
        </main>

      </div>
    </div>
  );
}
