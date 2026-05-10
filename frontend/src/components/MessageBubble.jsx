import QueryDisplay from './QueryDisplay'
import ResultTable from './ResultTable'

export default function MessageBubble({ message, onUserClick }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-xl bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-lg shadow-indigo-600/20">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start mb-8">
      <div className="max-w-4xl w-full space-y-4">
        <div className="flex items-center gap-2 px-1">
          <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 shadow-sm">
            K
          </div>
          <span className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">KumoRFM</span>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl px-4 py-3 shadow-sm">
          <p className="text-sm text-slate-200 leading-relaxed">
            {message.summary || message.content}
          </p>
        </div>

        {message.pql_query && (
          <div className="transition-all duration-300">
            <QueryDisplay
              pqlQuery={message.pql_query}
              queryType={message.query_type}
            />
          </div>
        )}

        {message.results && message.results.length > 0 && (
          <div className="transition-all duration-300">
            <ResultTable
              results={message.results}
              columns={message.columns || []}
              queryType={message.query_type}
              totalResults={message.total_results || message.results.length}
              onCustomerClick={onUserClick}
            />
          </div>
        )}
      </div>
    </div>
  )
}
