import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import ExampleQuestions from './ExampleQuestions'

export default function ChatWindow({ messages, isLoading, error, onSend, onCustomerClick, onAgentAction }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const showExamples = messages.length === 0 && !isLoading

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {showExamples ? (
          <ExampleQuestions onSelect={onSend} />
        ) : (
          <>
            {messages.map((msg, idx) => (
              <MessageBubble
                key={idx}
                message={msg}
                onCustomerClick={onCustomerClick}
                onAgentAction={onAgentAction}
              />
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
                    K
                  </div>
                  <div className="flex gap-1 items-center bg-slate-800 border border-slate-700 rounded-xl px-4 py-3">
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="flex justify-start">
                <div className="max-w-lg bg-red-950/50 border border-red-800 rounded-xl px-4 py-3 text-sm text-red-300">
                  <span className="font-semibold">Error:</span> {error}
                </div>
              </div>
            )}
          </>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
