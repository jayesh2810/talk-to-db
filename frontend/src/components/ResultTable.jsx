import { useState } from 'react'

function ScoreBadge({ score }) {
  const pct = Math.round(score * 100)
  let color = 'bg-emerald-900 text-emerald-300 border-emerald-700'
  if (pct >= 70) color = 'bg-red-900 text-red-300 border-red-700'
  else if (pct >= 40) color = 'bg-yellow-900 text-yellow-300 border-yellow-700'

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono font-bold border ${color}`}>
      {pct}%
    </span>
  )
}

function FactorsList({ factors }) {
  if (!Array.isArray(factors) || factors.length === 0) return <span className="text-gray-500">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {factors.map((f, i) => (
        <span key={i} className="text-xs px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-400 font-mono">
          {f.factor?.replace(/_/g, ' ')}
        </span>
      ))}
    </div>
  )
}

function CellValue({ col, value }) {
  if (value === null || value === undefined || value === '') {
    return <span className="text-gray-600">—</span>
  }

  if (col === 'score') return <ScoreBadge score={value} />

  if (col === 'top_factors') return <FactorsList factors={value} />

  if (col === 'confidence') {
    const pct = Math.round(value * 100)
    return <span className="text-gray-400 font-mono text-xs">{pct}%</span>
  }

  if (col === 'total_amount' || col === 'lifetime_value' || col === 'predicted_revenue' || col === 'total_revenue') {
    const num = parseFloat(value)
    return <span className="font-mono">${isNaN(num) ? value : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
  }

  if (typeof value === 'number') {
    return <span className="font-mono">{value.toLocaleString()}</span>
  }

  return <span>{String(value)}</span>
}

export default function ResultTable({ results, columns, queryType, totalResults }) {
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('desc')

  if (!results || results.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 p-6 text-center text-gray-500 text-sm">
        No results found.
      </div>
    )
  }

  const visibleColumns = columns.filter(c => c !== 'customer_id' && c !== 'order_id' && c !== 'product_id')

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('desc')
    }
  }

  let rows = [...results]
  if (sortCol) {
    rows.sort((a, b) => {
      const av = a[sortCol]
      const bv = b[sortCol]
      const an = typeof av === 'number' ? av : parseFloat(av) || 0
      const bn = typeof bv === 'number' ? bv : parseFloat(bv) || 0
      return sortDir === 'asc' ? an - bn : bn - an
    })
  }

  return (
    <div className="rounded-lg border border-gray-700 overflow-hidden">
      <div className="px-3 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
        <span className="text-xs text-gray-400 font-medium">Results</span>
        <span className="text-xs text-gray-500">
          Showing {rows.length} of {totalResults}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700 bg-gray-900">
              {visibleColumns.map(col => (
                <th
                  key={col}
                  onClick={() => !['top_factors'].includes(col) && handleSort(col)}
                  className={`px-3 py-2 text-left text-xs font-medium text-gray-400 whitespace-nowrap
                    ${!['top_factors'].includes(col) ? 'cursor-pointer hover:text-gray-200 select-none' : ''}
                  `}
                >
                  <span className="flex items-center gap-1">
                    {col.replace(/_/g, ' ')}
                    {sortCol === col && (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d={sortDir === 'asc' ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
                      </svg>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors"
              >
                {visibleColumns.map(col => (
                  <td key={col} className="px-3 py-2 text-gray-300 max-w-xs">
                    <CellValue col={col} value={row[col]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
