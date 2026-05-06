import { useState, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import CustomerDrawer from './components/CustomerDrawer'
import GraphVisualization from './components/GraphVisualization'
import { useChat } from './hooks/useChat'
import { AuthProvider, useAuth } from './context/AuthContext'
import AuthModal from './components/AuthModal'

function AppContent() {
  const { messages, isLoading, error, sendMessage, clearHistory } = useChat()
  const [input, setInput] = useState('')
  const [selectedCustomerId, setSelectedCustomerId] = useState(null)
  const [activeTab, setActiveTab] = useState('chat')
  const inputRef = useRef(null)

  const handleSubmit = async (text) => {
    const msg = (text || input).trim()
    if (!msg) return
    setInput('')
    await sendMessage(msg)
    inputRef.current?.focus()
  }

  const handleAgentAction = async (action, message) => {
    const workflowId = message?.workflow_id || ''
    if (action === 'approve') {
      await sendMessage(`/goal approve ${workflowId}`.trim(), { appendUser: false })
      return
    }
    if (action === 'revise') {
      const hint = message?.stage === 'assumptions'
        ? 'Example: uplift 15 reach 40 45 days'
        : 'What should be revised?'
      const revision = window.prompt(hint)
      if (!revision || !revision.trim()) return
      await sendMessage(`/goal revise ${workflowId} ${revision.trim()}`.trim(), { appendUser: false })
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-200">
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md z-10">
        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-base font-bold text-white shadow-lg shadow-indigo-500/20">
            K
          </div>
          <div>
             <h1 className="text-sm font-bold text-white leading-none tracking-tight">Relational Fonudatinal Model Test</h1>
            <p className="text-[11px] text-slate-500 leading-none mt-1 font-medium uppercase tracking-wider">Intelligence Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {activeTab === 'chat' && messages.length > 0 && (
            <button
              onClick={clearHistory}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors font-medium"
            >
              Clear Session
            </button>
          )}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-tighter">Graph Online</span>
          </div>
        </div>
      </header>

      <div className="flex-shrink-0 flex border-b border-slate-800 bg-slate-900/50 px-5">
        <button
          type="button"
          onClick={() => setActiveTab('chat')}
          className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'chat'
              ? 'text-indigo-400 border-indigo-500'
              : 'text-slate-500 border-transparent hover:text-slate-300'
          }`}
        >
          Chat
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('graph')}
          className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'graph'
              ? 'text-indigo-400 border-indigo-500'
              : 'text-slate-500 border-transparent hover:text-slate-300'
          }`}
        >
          Graph Knowledge
        </button>
      </div>

      {activeTab === 'chat' ? (
        <>
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <ChatWindow
              messages={messages}
              isLoading={isLoading}
              error={error}
              onSend={handleSubmit}
              onCustomerClick={setSelectedCustomerId}
              onAgentAction={handleAgentAction}
            />
          </div>

          <CustomerDrawer
            customerId={selectedCustomerId}
            onClose={() => setSelectedCustomerId(null)}
          />

          <div className="flex-shrink-0 border-t border-slate-800 bg-slate-900/50 backdrop-blur-md px-4 py-4">
            <div className="max-w-4xl mx-auto flex items-end gap-3">
              <div className="flex-1 relative group">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask a predictive question about your customers, orders, or products..."
                  rows={1}
                  disabled={isLoading}
                  className="
                    w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3
                    text-sm text-slate-200 placeholder-slate-500
                    resize-none focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50
                    disabled:opacity-50 disabled:cursor-not-allowed
                    transition-all duration-200 leading-relaxed
                  "
                  style={{ minHeight: '48px', maxHeight: '150px' }}
                  onInput={e => {
                    e.target.style.height = 'auto'
                    e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px'
                  }}
                />
              </div>
              <button
                type="button"
                onClick={() => handleSubmit()}
                disabled={isLoading || !input.trim()}
                className="
                  flex-shrink-0 w-11 h-11 rounded-xl bg-indigo-600 hover:bg-indigo-500
                  disabled:opacity-40 disabled:cursor-not-allowed
                  flex items-center justify-center transition-all duration-200
                  shadow-lg shadow-indigo-600/20 active:scale-95
                "
              >
                {isLoading ? (
                  <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-center text-[10px] text-slate-600 mt-3 font-mono tracking-tight uppercase">
              NL <span className="text-slate-700">→</span> PQL <span className="text-slate-700">→</span> KumoRFM <span className="text-slate-700">→</span> Summary
            </p>
          </div>
        </>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <GraphVisualization />
        </div>
      )}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
      <AuthGate />
    </AuthProvider>
  )
}

function AuthGate() {
  const { isAuthenticated } = useAuth()
  return !isAuthenticated ? <AuthModal /> : null
}
