import { useState, useCallback } from 'react'
import { AUTH_HEADER } from '../utils/auth'

const API_BASE = '/api'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = useCallback(async (text, options = {}) => {
    if (!text.trim() || isLoading) return
    const { appendUser = true } = options

    const userMessage = { role: 'user', content: text }

    if (appendUser) {
      setMessages(prev => [...prev, userMessage])
    }
    setIsLoading(true)
    setError(null)

    const history = messages.map(m => ({ role: m.role, content: m.content }))

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': AUTH_HEADER,
        },
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
        mode: data.mode || 'standard',
        workflow_id: data.workflow_id || null,
        stage: data.stage || null,
        pending_approval: data.pending_approval || null,
        proposal: data.proposal || null,
        execution_summary: data.execution_summary || null,
        agent_logs: data.agent_logs || [],
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setError(err.message)
      if (appendUser) {
        setMessages(prev => prev.slice(0, -1))
      }
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
