import React from 'react'

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

export default function ComparisonView({ data, onError }) {
  if (!data) return null

  const { graph_results, sql_results, deltas } = data

  const getRankChangeColor = (name) => {
    const delta = deltas.find(d => d.name === name)
    if (!delta) return 'border-transparent'
    if (delta.rank_change >= 2) return 'border-l-4 border-l-emerald-500'
    if (delta.rank_change <= -2) return 'border-l-4 border-l-red-500'
    return 'border-transparent'
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        {/* Graph Column */}
        <div className="space-y-2">
          <div className="px-3 py-2 bg-indigo-500/10 border border-indigo-500/20 rounded-t-xl text-center">
            <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest">Graph Score (with peer signal)</span>
          </div>
          <div className="border border-gray-700/50 rounded-b-xl overflow-hidden bg-gray-900/30">
            {graph_results.map((row, i) => (
              <div 
                key={i} 
                className={`flex items-center justify-between px-4 py-2 border-b border-gray-800/50 text-sm ${getRankChangeColor(row.name)}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-gray-500 font-mono text-xs w-4">{row.rank}.</span>
                  <span className="text-gray-200">{row.name}</span>
                </div>
                <ScoreBadge score={row.score} />
              </div>
            ))}
          </div>
        </div>

        {/* SQL Column */}
        <div className="space-y-2">
          <div className="px-3 py-2 bg-gray-700/20 border border-gray-700/50 rounded-t-xl text-center">
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">SQL Score (direct attributes)</span>
          </div>
          <div className="border border-gray-700/50 rounded-b-xl overflow-hidden bg-gray-900/30">
            {sql_results.map((row, i) => (
              <div 
                key={i} 
                className={`flex items-center justify-between px-4 py-2 border-b border-gray-800/50 text-sm ${getRankChangeColor(row.name)}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-gray-500 font-mono text-xs w-4">{row.rank}.</span>
                  <span className="text-gray-200">{row.name}</span>
                </div>
                <ScoreBadge score={row.score} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Biggest Movers */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 px-1">
          <span className="text-[11px] text-gray-500 font-bold uppercase tracking-wider">Biggest Movers</span>
          <div className="h-px flex-1 bg-gray-800"></div>
        </div>
        <div className="grid grid-cols-1 gap-2">
          {deltas.slice(0, 3).map((delta, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-gray-800/30 border border-gray-700/50 rounded-xl">
              <span className="text-sm text-gray-300">
                <span className="font-bold text-white">{delta.name}</span>
                <span className="text-gray-500 ml-2">shifted {Math.abs(delta.rank_change)} positions</span>
              </span>
              <div className={`text-xs font-mono px-2 py-0.5 rounded ${delta.rank_change > 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-red-400 bg-red-500/10'}`}>
                {delta.rank_change > 0 ? `↑ ${delta.rank_change}` : `↓ ${Math.abs(delta.rank_change)}`}
              </div>
            </div>
          ))}
          {deltas.length === 0 && (
            <div className="text-center py-4 text-gray-600 text-xs italic">
              No significant rank changes detected.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
