import { useState } from 'react'

function ScoreBadge({ score }) {
  const pct = Math.round(score * 100)
  let color = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
  if (pct >= 70) color = 'bg-red-500/10 text-red-400 border-red-500/30'
  else if (pct >= 40) color = 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-bold border ${color} shadow-sm`}>
      {pct}%
    </span>
  )
}

function PrescriptionBadge({ action, probability }) {
  const probPct = Math.round((probability || 0) * 100)
  const isHighProb = probPct >= 50
  
  return (
    <div className="flex flex-col gap-1">
      <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium ${
        isHighProb 
          ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30' 
          : 'bg-gray-800/50 text-gray-400 border-gray-700'
      }`}>
        {action}
      </span>
      <span className="text-[9px] text-gray-500 font-mono">
        Prob: {probPct}%
      </span>
    </div>
  )
}

function FactorsList({ factors }) {
  if (!Array.isArray(factors) || factors.length === 0) return <span className="text-gray-600">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {factors.map((f, i) => (
        <span key={i} className="text-[10px] px-1.5 py-0.5 bg-gray-800/50 border border-gray-700 rounded text-gray-400 font-mono">
          {f.factor?.replace(/_/g, ' ')}
        </span>
      ))}
    </div>
  )
}

function exportToCsv(columns, rows, filename) {
  const filteredCols = columns.filter(c => !c.startsWith('_'))
  const headers = filteredCols.join(',')
  
  const csvRows = rows.map(row => {
    return filteredCols.map(col => {
      let val = row[col]
      if (col === 'top_factors' && Array.isArray(val)) {
        val = val.map(f => `${f.factor}(${f.contribution})`).join(', ')
      }
      
      let strVal = val === null || val === undefined ? '' : String(val)
      if (strVal.includes(',') || strVal.includes('\n') || strVal.includes('"')) {
        strVal = `"${strVal.replace(/"/g, '""')}"`
      }
      return strVal
    }).join(',')
  })

  const csvContent = [headers, ...csvRows].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function CellValue({ col, value, row }) {
  if (value === null || value === undefined || value === '') {
    return <span className="text-gray-600">—</span>
  }

  if (col === 'score') return <ScoreBadge score={value} />

  if (col === 'recommended_action') return <PrescriptionBadge action={value} probability={row.success_probability} />

  if (col === 'top_factors') return <FactorsList factors={value} />

  if (col === 'confidence') {
    const pct = Math.round(value * 100)
    return <span className="text-gray-400 font-mono text-xs">{pct}%</span>
  }

  if (col === 'total_amount' || col === 'lifetime_value' || col === 'predicted_revenue' || col === 'total_revenue') {
    const num = parseFloat(value)
    return <span className="font-mono text-gray-200">${isNaN(num) ? value : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
  }

  if (typeof value === 'number') {
    return <span className="font-mono text-gray-200">{value.toLocaleString()}</span>
  }

  return <span className="text-gray-300">{String(value)}</span>
}

export default function ResultTable({ results, columns, queryType, totalResults, onCustomerClick }) {
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('desc')

  if (!results || results.length === 0) {
    return (
      <div className="rounded-2xl border border-gray-700/50 p-8 text-center text-gray-500 text-sm bg-gray-900/20">
        No results found.
      </div>
    )
  }

  const visibleColumns = columns.filter(c => c !== 'customer_id' && c !== 'order_id' && c !== 'product_id' && c !== 'success_probability')
  const isCustomerQuery = queryType?.includes('customer') || columns.includes('customer_id')

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
    <div className="rounded-2xl border border-gray-700/50 overflow-hidden bg-gray-900/30 shadow-xl">
      <div className="px-4 py-3 bg-gray-800/50 border-b border-gray-700/50 flex items-center justify-between">
        <span className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">Query Results</span>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-gray-500 font-medium">
            Showing {rows.length} of {totalResults}
          </span>
          <button 
            onClick={() => {
              const filename = `kumorfm-${queryType}-${new Date().toISOString().split('T')[0]}.csv`
              exportToCsv(columns, rows, filename)
            }}
            className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:border-gray-400 transition-colors flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700/50 bg-gray-900/50">
              {visibleColumns.map(col => (
                <th
                  key={col}
                  onClick={() => !['top_factors'].includes(col) && handleSort(col)}
                  className={`px-4 py-3 text-left text-[11px] font-bold text-gray-500 uppercase tracking-wider whitespace-nowrap
                    ${!['top_factors'].includes(col) ? 'cursor-pointer hover:text-gray-300 select-none transition-colors' : ''}
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
              {isCustomerQuery && <th className="w-10"></th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                onClick={() => isCustomerQuery && onCustomerClick?.(row.customer_id)}
                className={`border-b border-gray-800/50 transition-all ${
                  isCustomerQuery ? 'cursor-pointer hover:bg-indigo-500/5' : 'hover:bg-gray-800/30'
                }`}
              >
                {visibleColumns.map(col => (
                  <td key={col} className="px-4 py-3 text-gray-300 max-w-xs">
                    <CellValue col={col} value={row[col]} row={row} />
                  </td>
                ))}
                {isCustomerQuery && (
                  <td className="px-4 py-3 text-gray-600 text-center">
                    <svg className="w-4 h-4 inline opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
