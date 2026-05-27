import { useState } from 'react'
import { exportToCsv, sendToWebhook } from '../utils/exportUtils'

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

function FactorsList({ factors }) {
  if (!Array.isArray(factors) || factors.length === 0) return <span className="text-gray-600">-</span>
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

function ExportModal({ isOpen, onClose, columns, rows, queryType }) {
  const [webhookUrl, setWebhookUrl] = useState('')
  const [isSending, setIsSending] = useState(false)

  if (!isOpen) return null

  const handleCsvExport = (type) => {
    const filename = type === 'standard' 
      ? `talk-to-db-${queryType}-${new Date().toISOString().split('T')[0]}.csv`
      : `campaign-export-${queryType}-${new Date().toISOString().split('T')[0]}.csv`
    
    // For campaign export, we could filter columns to only essential ones (email, score, etc.)
    // but for MVP we'll use the same function.
    exportToCsv(columns, rows, filename)
    onClose()
  }

  const handleWebhookSend = async () => {
    if (!webhookUrl) return
    setIsSending(true)
    try {
      await sendToWebhook(webhookUrl, {
        query_type: queryType,
        results: rows,
        timestamp: new Date().toISOString()
      })
      alert('Campaign sent to webhook successfully!')
      onClose()
    } catch (e) {
      alert(`Error: ${e.message}`)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-gray-200">Export Campaign</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6 space-y-6">
          <div className="space-y-3">
            <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">Download CSV</p>
            <div className="grid grid-cols-2 gap-3">
              <button 
                onClick={() => handleCsvExport('standard')}
                className="text-xs p-3 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-all text-left"
              >
                <div className="font-bold mb-1">Standard</div>
                <div className="text-gray-500">Full query results</div>
              </button>
              <button 
                onClick={() => handleCsvExport('campaign')}
                className="text-xs p-3 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-all text-left"
              >
                <div className="font-bold mb-1">Campaign</div>
                <div className="text-gray-500">Optimized for CRM</div>
              </button>
            </div>
          </div>
          <div className="space-y-3">
            <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">Automate via Webhook</p>
            <div className="flex gap-2">
              <input 
                type="text" 
                placeholder="https://hooks.zapier.com/..." 
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <button 
                onClick={handleWebhookSend}
                disabled={isSending || !webhookUrl}
                className="px-4 py-2 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-500 disabled:opacity-50 transition-colors"
              >
                {isSending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function CellValue({ col, value }) {

  if (value === null || value === undefined || value === '') {
    return <span className="text-gray-600">-</span>
  }

  if (col === 'score') return <ScoreBadge score={value} />

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
  const [isExportOpen, setIsExportOpen] = useState(false)

  if (!results || results.length === 0) {
    return (
      <div className="rounded-2xl border border-gray-700/50 p-8 text-center text-gray-500 text-sm bg-gray-900/20">
        No results found.
      </div>
    )
  }

  const visibleColumns = columns
  const isCustomerQuery = columns.includes('user_id')

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
             onClick={() => setIsExportOpen(true)}
             className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:border-gray-400 transition-colors flex items-center gap-1"
           >
             <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
             </svg>
             Export Campaign
           </button>
         </div>
       </div>
       <ExportModal 
         isOpen={isExportOpen} 
         onClose={() => setIsExportOpen(false)} 
         columns={columns} 
         rows={rows} 
         queryType={queryType} 
       />

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
                onClick={() => isCustomerQuery && row.user_id != null && onCustomerClick?.(row.user_id)}
                className={`border-b border-gray-800/50 transition-all ${
                  isCustomerQuery ? 'cursor-pointer hover:bg-indigo-500/5' : 'hover:bg-gray-800/30'
                }`}
              >
                {visibleColumns.map(col => (
                  <td key={col} className="px-4 py-3 text-gray-300 max-w-xs">
                    <CellValue col={col} value={row[col]} />
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
