import { useState, useCallback } from 'react'

const API_BASE = '/api'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || isLoading) return

    const userMessage = { role: 'user', content: text }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setError(null)

    const history = messages.map(m => ({ role: m.role, content: m.content }))

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()

      const assistantMessage = {
        role: 'assistant',
        content: data.summary,
        pql_query: data.pql_query,
        query_type: data.query_type,
        results: data.results,
        columns: data.columns,
        total_results: data.total_results,
        summary: data.summary,
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setError(err.message)
      setMessages(prev => prev.slice(0, -1))
    } finally {
      setIsLoading(false)
    }
  }, [messages, isLoading])

  const clearHistory = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, isLoading, error, sendMessage, clearHistory }
}
