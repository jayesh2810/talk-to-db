import { useState, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import GraphVisualization from './components/GraphVisualization'
import { useChat } from './hooks/useChat'

export default function App() {
  const { messages, isLoading, error, sendMessage, clearHistory } = useChat()
  const [input, setInput] = useState('')
  const [activeTab, setActiveTab] = useState('chat')
  const inputRef = useRef(null)

  const handleSubmit = async (text) => {
    const msg = (text || input).trim()
    if (!msg) return
    setInput('')
    await sendMessage(msg)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-950">
      {/* Top bar */}
      <header className="flex-shrink-0 flex items-center justify-between px-5 py-3 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-sm font-bold text-white">
            K
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white leading-none">KumoRFM Demo</h1>
            <p className="text-xs text-gray-500 leading-none mt-0.5">Relational Predictive Analytics</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {activeTab === 'chat' && messages.length > 0 && (
            <button
              onClick={clearHistory}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Clear
            </button>
          )}
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs text-gray-500">Graph loaded</span>
          </div>
        </div>
      </header>

      {/* Tab navigation */}
      <div className="flex-shrink-0 flex border-b border-gray-800 bg-gray-900 px-5">
        <button
          onClick={() => setActiveTab('chat')}
          className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'chat'
              ? 'text-indigo-400 border-indigo-500'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          Chat
        </button>
        <button
          onClick={() => setActiveTab('graph')}
          className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'graph'
              ? 'text-indigo-400 border-indigo-500'
              : 'text-gray-500 border-transparent hover:text-gray-300'
          }`}
        >
          Graph Knowledge
        </button>
      </div>

      {/* Content area */}
      {activeTab === 'chat' ? (
        <>
          {/* Chat area */}
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            error={error}
            onSend={handleSubmit}
          />

          {/* Input bar */}
          <div className="flex-shrink-0 border-t border-gray-800 bg-gray-900 px-4 py-3">
            <div className="max-w-4xl mx-auto flex items-end gap-3">
              <div className="flex-1 relative">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask a predictive question about your customers, orders, or products..."
                  rows={1}
                  disabled={isLoading}
                  className="
                    w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3
                    text-sm text-gray-200 placeholder-gray-600
                    resize-none focus:outline-none focus:border-indigo-500
                    disabled:opacity-50 disabled:cursor-not-allowed
                    transition-colors leading-relaxed
                  "
                  style={{ minHeight: '44px', maxHeight: '120px' }}
                  onInput={e => {
                    e.target.style.height = 'auto'
                    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
                  }}
                />
              </div>
              <button
                onClick={() => handleSubmit()}
                disabled={isLoading || !input.trim()}
                className="
                  flex-shrink-0 w-10 h-10 rounded-xl bg-indigo-600 hover:bg-indigo-500
                  disabled:opacity-40 disabled:cursor-not-allowed
                  flex items-center justify-center transition-colors
                "
              >
                {isLoading ? (
                  <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-center text-xs text-gray-700 mt-2">
              NL → PQL → Graph Traversal → Prediction → Summary
            </p>
          </div>
        </>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <GraphVisualization />
        </div>
      )}
    </div>
  )
}
