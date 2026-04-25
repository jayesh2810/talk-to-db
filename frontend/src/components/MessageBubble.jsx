import QueryDisplay from './QueryDisplay'
import TraversalSteps from './TraversalSteps'
import ResultTable from './ResultTable'

export default function MessageBubble({ message, onCustomerClick }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-xl bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    )
  }

  // Assistant message — structured layout
  return (
    <div className="flex justify-start">
      <div className="max-w-4xl w-full space-y-3">
        {/* Avatar + name */}
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
            K
          </div>
          <span className="text-xs text-gray-500 font-medium">Relational Predictive Analytics Demo</span>
        </div>

        {/* 1. Plain-English Summary (read first) */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3">
          <p className="text-sm text-gray-200 leading-relaxed">
            {message.summary || message.content}
          </p>
        </div>

        {/* 2. PQL Query block */}
        {message.pql_query && (
          <QueryDisplay
            pqlQuery={message.pql_query}
            queryType={message.query_type}
          />
        )}

        {/* 3. Traversal Steps (predictive only) */}
        {message.traversal_steps && message.traversal_steps.length > 0 && (
          <TraversalSteps steps={message.traversal_steps} />
        )}

        {/* 4. Results Table */}
        {message.results && message.results.length > 0 && (
          <ResultTable
            results={message.results}
            columns={message.columns || []}
            queryType={message.query_type}
            totalResults={message.total_results || message.results.length}
            onCustomerClick={onCustomerClick}
          />
        )}
      </div>
    </div>
  )
}
