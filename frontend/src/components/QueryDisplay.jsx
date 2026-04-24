import { useState } from 'react'

const TYPE_BADGE = {
  predictive: 'bg-indigo-900 text-indigo-300 border border-indigo-700',
  factual:    'bg-emerald-900 text-emerald-300 border border-emerald-700',
}

export default function QueryDisplay({ pqlQuery, queryType }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="rounded-lg border border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800 hover:bg-gray-750 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-medium">Query generated</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-mono font-medium ${TYPE_BADGE[queryType] || TYPE_BADGE.factual}`}>
            {queryType === 'predictive' ? 'PREDICT' : 'MATCH'}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <pre className="p-3 bg-gray-900 text-sm font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap leading-relaxed border-t border-gray-700">
          {pqlQuery}
        </pre>
      )}
    </div>
  )
}
