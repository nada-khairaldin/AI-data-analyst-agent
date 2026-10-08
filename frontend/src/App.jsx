import { useState, useEffect, useRef } from 'react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ScatterChart, Scatter
} from 'recharts'

const COLORS = ['#aa3bff', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899']

const ChartRenderer = ({ chartPlan, data }) => {
  // Prevent crash if data is not an array (e.g. if the result was a single number or string)
  if (!chartPlan || !chartPlan.should_plot || !data || !Array.isArray(data) || data.length === 0) {
    return null
  }

  const { chart_type, x, y } = chartPlan

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white dark:bg-slate-800 p-3 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 text-sm">
          <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1">{`${x}: ${label || payload[0].payload[x]}`}</p>
          {payload.map((entry, index) => (
            <p key={index} style={{ color: entry.color }}>
              {`${entry.name}: ${entry.value}`}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  const renderChart = () => {
    switch (chart_type) {
      case 'bar':
        return (
          <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey={x} tick={{ fill: '#64748b' }} axisLine={{ stroke: '#cbd5e1' }} />
            <YAxis tick={{ fill: '#64748b' }} axisLine={{ stroke: '#cbd5e1' }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Bar dataKey={y} fill="#aa3bff" radius={[4, 4, 0, 0]} animationDuration={1500} />
          </BarChart>
        )
      case 'line':
        return (
          <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey={x} tick={{ fill: '#64748b' }} axisLine={{ stroke: '#cbd5e1' }} />
            <YAxis tick={{ fill: '#64748b' }} axisLine={{ stroke: '#cbd5e1' }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line type="monotone" dataKey={y} stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} animationDuration={1500} />
          </LineChart>
        )
      case 'pie':
        return (
          <PieChart>
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Pie
              data={data}
              dataKey={y}
              nameKey={x}
              cx="50%"
              cy="50%"
              outerRadius={100}
              fill="#8884d8"
              label
              animationDuration={1500}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        )
      case 'scatter':
        return (
          <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis type="number" dataKey={x} name={x} tick={{ fill: '#64748b' }} />
            <YAxis type="number" dataKey={y} name={y} tick={{ fill: '#64748b' }} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<CustomTooltip />} />
            <Legend />
            <Scatter name={`${y} vs ${x}`} data={data} fill="#10b981" animationDuration={1500} />
          </ScatterChart>
        )
      default:
        return (
          <div className="p-4 text-center text-slate-500">
            نوع الرسم البياني غير مدعوم: {chart_type}
          </div>
        )
    }
  }

  return (
    <div className="w-full h-80 mt-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800 p-4 shadow-sm" dir="ltr">
      <h3 className="text-center font-medium text-slate-600 dark:text-slate-400 mb-4">{`${y} by ${x}`}</h3>
      <ResponsiveContainer width="100%" height="90%">
        {renderChart()}
      </ResponsiveContainer>
    </div>
  )
}

function App() {
  const [darkMode, setDarkMode] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [fileReport, setFileReport] = useState(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Handle Dark mode class toggling
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  const toggleDarkMode = () => setDarkMode(!darkMode)

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setIsUploading(true)
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('http://127.0.0.1:8000/api/upload', {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      
      if (data.status === 'success') {
        setSessionId(data.session_id)
        setFileReport({
          rowCount: data.row_count,
          columnCount: data.column_count,
          schema: data.schema,
          conversions: data.conversions,
          warnings: data.warnings,
          unavailableColumns: data.unavailable_columns
        })
        setIsSidebarOpen(true)
        setMessages([{
          role: 'system',
          content: 'تم رفع الملف بنجاح! تفضل بطرح أسئلتك حول البيانات 🚀'
        }])
      } else {
        alert(data.message || 'حدث خطأ أثناء رفع الملف')
      }
    } catch (err) {
      alert("فشل الاتصال بالسيرفر. تأكد من تشغيل FastAPI.")
    } finally {
      setIsUploading(false)
    }
  }

  const handleSend = async (e) => {
    e?.preventDefault()
    if (!input.trim() || !sessionId) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsAnalyzing(true)

    try {
      const res = await fetch('http://127.0.0.1:8000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, query: userMessage })
      })
      const data = await res.json()

      if (data.status === 'success') {
        setMessages(prev => [...prev, { 
          role: 'agent', 
          content: data.answer,
          plan: data.analysis_plan,
          chartPlan: data.chart_plan,
          resultData: data.result_data
        }])
      } else if (data.status === 'error') {
        setMessages(prev => [...prev, { role: 'error', content: data.message }])
      } else {
        setMessages(prev => [...prev, { role: 'warning', content: data.message }])
      }
    } catch (err) {
       setMessages(prev => [...prev, { role: 'error', content: "حدث خطأ في الاتصال بالذكاء الاصطناعي." }])
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 transition-colors duration-300 font-sans" dir="rtl">
      
      {/* Navbar */}
      <header className="flex items-center justify-between px-6 py-4 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 sticky top-0 z-50">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent flex items-center gap-2">
          <svg className="w-6 h-6 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Data AI Agent
        </h1>
        
        <div className="flex items-center gap-4">
          {fileReport && !isSidebarOpen && (
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="px-3 py-1.5 flex items-center gap-2 rounded-full bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/50 transition border border-purple-200 dark:border-purple-800/50"
              title="عرض تفاصيل البيانات"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
              <span className="text-sm font-medium hidden sm:block">تفاصيل الملف</span>
            </button>
          )}
          <label className="cursor-pointer flex items-center gap-2 bg-slate-100 dark:bg-slate-800 px-4 py-2 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 transition">
            <svg className="w-5 h-5 text-slate-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {isUploading ? 'جاري الرفع...' : 'رفع ملف CSV'}
            </span>
            <input type="file" accept=".csv" className="hidden" onChange={handleFileUpload} disabled={isUploading} />
          </label>

          <button 
            onClick={toggleDarkMode}
            className="p-2 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
          >
            {darkMode ? (
              <svg className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4.22 2.28a1 1 0 011.415 0l.708.708a1 1 0 01-1.414 1.414l-.708-.708a1 1 0 010-1.414zM17 10a1 1 0 011 1h-1a1 1 0 110-2h1a1 1 0 01-1 1zm-2.28 4.22a1 1 0 010 1.415l-.708.708a1 1 0 01-1.414-1.414l.708-.708a1 1 0 011.414 0zM10 16a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm-4.22-2.28a1 1 0 01-1.415 0l-.708-.708a1 1 0 011.414-1.414l.708.708a1 1 0 010 1.415zM3 10a1 1 0 01-1-1h1a1 1 0 110 2H2a1 1 0 011-1zm2.28-4.22a1 1 0 010-1.415l.708-.708a1 1 0 011.414 1.414l-.708.708a1 1 0 01-1.414 0zM10 5a5 5 0 100 10 5 5 0 000-10z" /></svg>
            ) : (
              <svg className="w-5 h-5 text-slate-700" fill="currentColor" viewBox="0 0 20 20"><path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" /></svg>
            )}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className={`${isSidebarOpen && fileReport ? 'w-80 md:w-96 border-l border-slate-200 dark:border-slate-800 opacity-100' : 'w-0 border-transparent opacity-0'} transition-all duration-300 overflow-hidden bg-white dark:bg-slate-900/50 flex flex-col z-10 shrink-0`}>
          {fileReport && (
            <div className="p-4 h-full overflow-y-auto w-80 md:w-96 flex flex-col gap-4 scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-700">
              <div className="flex justify-between items-center mb-1">
                <h2 className="text-lg font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                  معلومات الملف
                </h2>
                <button onClick={() => setIsSidebarOpen(false)} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full text-slate-500 transition-colors" title="إغلاق اللوحة">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>

              {/* Rows and columns cards */}
              <div className="flex gap-3">
                <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-200/50 dark:border-slate-700 flex-1 text-center shadow-sm">
                  <div className="text-slate-500 dark:text-slate-400 text-xs mb-1 font-semibold">عدد الصفوف</div>
                  <div className="text-xl font-bold text-slate-800 dark:text-slate-200">{fileReport.rowCount.toLocaleString()}</div>
                </div>
                <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-200/50 dark:border-slate-700 flex-1 text-center shadow-sm">
                  <div className="text-slate-500 dark:text-slate-400 text-xs mb-1 font-semibold">عدد الأعمدة</div>
                  <div className="text-xl font-bold text-slate-800 dark:text-slate-200">{fileReport.columnCount.toLocaleString()}</div>
                </div>
              </div>

              {/* Schema Table */}
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-sm flex flex-col flex-shrink-0" style={{ maxHeight: '250px' }}>
                <div className="bg-slate-50 dark:bg-slate-900/80 px-3 py-2 border-b border-slate-200 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-300 text-sm flex items-center gap-2 shrink-0">
                  <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
                  هيكل البيانات (Schema)
                </div>
                <div className="overflow-y-auto flex-1 scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-700">
                  <table className="w-full text-right text-xs border-collapse">
                    <thead className="bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 sticky top-0 shadow-sm z-10">
                      <tr>
                        <th className="px-3 py-2 font-medium">العمود</th>
                        <th className="px-3 py-2 font-medium">النوع</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                      {Object.entries(fileReport.schema).map(([col, type]) => (
                        <tr key={col} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300 font-medium truncate max-w-[140px]" title={col}>{col}</td>
                          <td className="px-3 py-2">
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">{type}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Conversions */}
              {fileReport.conversions && Object.keys(fileReport.conversions).length > 0 && (
                <div className="bg-blue-50/80 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-xl p-3 shadow-sm text-blue-900 dark:text-blue-100 text-xs flex-shrink-0">
                  <h4 className="font-bold mb-2 flex items-center gap-1.5">
                    <svg className="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    تحويلات الأنواع ({Object.keys(fileReport.conversions).length})
                  </h4>
                  <div className="space-y-1.5 max-h-[120px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-blue-200 dark:scrollbar-thumb-blue-800">
                    {Object.entries(fileReport.conversions).map(([col, info]) => (
                      <div key={col} className="bg-white/60 dark:bg-slate-800/50 rounded p-1.5 flex flex-wrap items-center gap-1 border border-blue-100 dark:border-blue-800/30">
                        <span className="font-bold text-blue-700 dark:text-blue-300 truncate max-w-[80px]" title={col}>{col}</span>
                        <span className="text-slate-400">&larr;</span>
                        <span className="font-mono bg-blue-100/50 dark:bg-blue-900/40 px-1 rounded text-blue-600 dark:text-blue-400">{info.converted_to}</span>
                        <span className="mr-auto text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">{(info.success_rate * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Unavailable columns */}
              {fileReport.unavailableColumns && Object.keys(fileReport.unavailableColumns).length > 0 && (
                <div className="bg-amber-50/80 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50 rounded-xl p-3 shadow-sm text-amber-900 dark:text-amber-100 text-xs flex-shrink-0 mt-auto">
                  <h4 className="font-bold mb-2 flex items-center gap-1.5">
                    <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                    أعمدة مستبعدة ({Object.keys(fileReport.unavailableColumns).length})
                  </h4>
                  <div className="space-y-1.5 max-h-[100px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-amber-200 dark:scrollbar-thumb-amber-800">
                    {Object.entries(fileReport.unavailableColumns).map(([col, reason]) => (
                      <div key={col} className="bg-white/60 dark:bg-slate-800/50 rounded p-1.5 flex items-start gap-1.5 border border-amber-100 dark:border-amber-800/30">
                        <span className="font-bold text-amber-700 dark:text-amber-400 truncate max-w-[70px]" title={col}>{col}</span>
                        <span className="text-slate-600 dark:text-slate-400 text-[10px] leading-tight flex-1">{reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </aside>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 relative">
          <main className="flex-1 w-full mx-auto p-4 md:p-6 flex flex-col gap-6 overflow-y-auto" style={{ height: 'calc(100vh - 160px)' }}>
            
            {messages.length === 0 && !sessionId && (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 dark:text-slate-400 gap-4">
                <div className="w-20 h-20 bg-slate-200 dark:bg-slate-800 rounded-full flex items-center justify-center mb-4 shadow-inner">
                  <svg className="w-10 h-10 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h2 className="text-2xl font-semibold text-slate-700 dark:text-slate-300">أهلاً بك في محلل البيانات الذكي</h2>
                <p className="max-w-md text-center">الرجاء رفع ملف CSV الخاص بك للبدء في استكشاف وتحليل بياناتك بذكاء وسهولة.</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl p-4 shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-gradient-to-br from-blue-600 to-purple-600 text-white rounded-br-none' 
                    : msg.role === 'system'
                    ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                    : msg.role === 'error'
                    ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800'
                    : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-none border border-slate-100 dark:border-slate-700'
                }`}>
                  
                  {/* Message Content */}
                  <div className="prose dark:prose-invert max-w-none text-sm md:text-base leading-relaxed whitespace-pre-wrap">
                    {typeof msg.content === 'object' ? JSON.stringify(msg.content, null, 2) : msg.content}
                  </div>

                  {/* Show Chart if available */}
                  {msg.chartPlan && msg.chartPlan.should_plot && msg.resultData && (
                    <ChartRenderer chartPlan={msg.chartPlan} data={msg.resultData} />
                  )}

                  {/* Show Plan if available */}
                  {msg.plan && (
                    <details className="mt-4 p-3 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 text-xs">
                      <summary className="font-semibold text-slate-500 flex items-center gap-1 cursor-pointer hover:text-slate-700 dark:hover:text-slate-300 transition-colors">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
                        كود خطة التحليل (اضغط للعرض)
                      </summary>
                      <pre className="mt-2 text-slate-600 dark:text-slate-400 font-mono overflow-x-auto whitespace-pre-wrap">
                        {typeof msg.plan === 'object' ? JSON.stringify(msg.plan, null, 2) : msg.plan}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}

            {isAnalyzing && (
              <div className="flex justify-start">
                <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-2xl rounded-bl-none p-4 shadow-sm flex gap-2 items-center">
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  <span className="text-sm text-slate-500 ml-2">الذكاء الاصطناعي يقوم بالتحليل...</span>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </main>

          {/* Input Area */}
          <div className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 p-4 sticky bottom-0">
            <form onSubmit={handleSend} className="max-w-4xl mx-auto flex gap-3 relative">
              <input 
                type="text" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!sessionId || isAnalyzing}
                placeholder={sessionId ? "اسأل أي شيء عن البيانات (مثال: ما هو متوسط المبيعات؟)" : "يرجى رفع ملف CSV أولاً..."}
                className="flex-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white rounded-full py-4 pl-6 pr-14 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 transition shadow-inner"
              />
              <button 
                type="submit" 
                disabled={!input.trim() || !sessionId || isAnalyzing}
                className="absolute left-2 top-2 bottom-2 bg-purple-600 hover:bg-purple-700 text-white rounded-full w-10 h-10 flex items-center justify-center disabled:opacity-50 transition transform active:scale-95 shadow-md"
              >
                <svg className="w-5 h-5 rtl:-scale-x-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </form>
          </div>
        </div>
      </div>

    </div>
  )
}

export default App
