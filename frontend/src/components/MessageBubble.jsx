import QueryDisplay from './QueryDisplay'
import TraversalSteps from './TraversalSteps'
import ResultTable from './ResultTable'

export default function MessageBubble({ message, onCustomerClick }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-xl bg-gradient-to-br from-indigo-600 to-violet-700 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-lg shadow-indigo-500/20">
          {message.content}
        </div>
      </div>
    )
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

        {/* 4. Results Table */}
        {message.results && message.results.length > 0 && (
          <div className="transition-all duration-300">
            <ResultTable
              results={message.results}
              columns={message.columns || []}
              queryType={message.query_type}
              totalResults={message.total_results || message.results.length}
              onCustomerClick={onCustomerClick}
            />
          </div>
        )}
      </div>
    </div>
  )
}
