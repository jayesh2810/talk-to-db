import { useState } from 'react'
import QueryDisplay from './QueryDisplay'
import TraversalSteps from './TraversalSteps'
import ResultTable from './ResultTable'
import ComparisonView from './ComparisonView'

export default function MessageBubble({ message, onCustomerClick }) {
  const [showComparison, setShowComparison] = useState(false)
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [comparisonData, setComparisonData] = useState(null)
  const [comparisonError, setComparisonError] = useState(null)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-xl bg-gradient-to-br from-indigo-600 to-violet-700 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-lg shadow-indigo-500/20">
          {message.content}
        </div>
      </div>
    )
  }

  const handleCompare = async () => {
    setComparisonLoading(true)
    setComparisonError(null)
    try {
      const response = await fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message.originalQuestion || message.content, // Fallback to content if originalQuestion is missing
          history: [], // In a real app, we'd pass the history
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to fetch comparison data')
      }

      const data = await response.json()
      setComparisonData(data)
      setShowComparison(true)
    } catch (err) {
      setComparisonError(err.message)
    } finally {
      setComparisonLoading(false)
    }
  }

  // Assistant message — structured layout
  return (
    <div className="flex justify-start mb-8">
      <div className="max-w-4xl w-full space-y-4">
        {/* Avatar + name */}
        <div className="flex items-center gap-2 px-1">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 shadow-sm">
            K
          </div>
          <span className="text-[11px] text-gray-500 font-bold uppercase tracking-wider">Intelligence Engine</span>
        </div>

        {/* 1. Plain-English Summary (read first) */}
        <div className="bg-gray-800/40 border border-gray-700/50 rounded-2xl px-4 py-3 shadow-sm">
          <p className="text-sm text-gray-200 leading-relaxed">
            {message.summary || message.content}
          </p>
        </div>

        {/* 2. PQL Query block */}
        {message.pql_query && (
          <div className="transition-all duration-300">
            <QueryDisplay
              pqlQuery={message.pql_query}
              queryType={message.query_type}
            />
          </div>
        )}

        {/* 3. Traversal Steps (predictive only) */}
        {message.traversal_steps && message.traversal_steps.length > 0 && (
          <div className="transition-all duration-300">
            <TraversalSteps steps={message.traversal_steps} />
          </div>
        )}

        {/* 4. Results or Comparison */}
        {message.results && message.results.length > 0 && (
          <div className="transition-all duration-300 space-y-3">
            {showComparison ? (
              <div className="space-y-3">
                {comparisonLoading ? (
                  <div className="p-8 text-center text-gray-500 text-sm bg-gray-900/20 rounded-2xl border border-gray-700/50">
                    Loading comparison...
                  </div>
                ) : comparisonError ? (
                  <div className="p-4 text-center text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-xl">
                    {comparisonError}
                  </div>
                ) : (
                  <ComparisonView data={comparisonData} />
                )}
                <button 
                  onClick={() => setShowComparison(false)}
                  className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1 ml-1"
                >
                  ← Back to results
                </button>
              </div>
            ) : (
              <>
                <ResultTable
                  results={message.results}
                  columns={message.columns || []}
                  queryType={message.query_type}
                  totalResults={message.total_results || message.results.length}
                  onCustomerClick={onCustomerClick}
                />
                {message.query_type === 'predictive' && (
                  <div className="flex justify-center">
                    <button
                      onClick={handleCompare}
                      className="text-[11px] px-3 py-1.5 rounded-full border border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10 hover:text-indigo-300 transition-all flex items-center gap-2 bg-indigo-500/5"
                    >
                      <span>⚡ Compare with flat SQL</span>
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
