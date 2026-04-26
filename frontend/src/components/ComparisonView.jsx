import React from 'react'

export default function ComparisonView({ data }) {
  const { deltas, summary } = data

  return (
    <div className="mt-4 space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="bg-indigo-950/30 border border-indigo-500/30 rounded-xl p-4">
        <h4 className="text-indigo-400 text-xs font-bold uppercase tracking-widest mb-2">Comparison Summary</h4>
        <p className="text-sm text-slate-300 leading-relaxed">{summary}</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 bg-slate-800/50">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Rank Deltas (Graph vs SQL)</h4>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-slate-500 border-b border-slate-800">
                <th className="px-4 py-2 font-medium">Customer</th>
                <th className="px-4 py-2 font-medium text-center">Graph Rank</th>
                <th className="px-4 py-2 font-medium text-center">SQL Rank</th>
                <th className="px-4 py-2 font-medium text-center">Rank Shift</th>
                <th className="px-4 py-2 font-medium text-right">Score Δ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {deltas.map((delta, idx) => (
                <tr key={idx} className="hover:bg-slate-800/50 transition-colors">
                  <td className="px-4 py-2 text-slate-200 font-medium">{delta.name}</td>
                  <td className="px-4 py-2 text-center text-indigo-400 font-bold">{delta.graph_rank}</td>
                  <td className="px-4 py-2 text-center text-slate-500">{delta.sql_rank}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      delta.rank_change > 0 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'
                    }`}>
                      {delta.rank_change > 0 ? `+${delta.rank_change}` : delta.rank_change}
                    </span>
                  </td>
                  <td className={`px-4 py-2 text-right font-mono ${delta.score_delta > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                    {delta.score_delta > 0 ? `+${delta.score_delta}` : delta.score_delta}
                  </td>
                </tr>
              ))}
              {deltas.length === 0 && (
                <tr>
                  <td colSpan="5" className="px-4 py-8 text-center text-slate-500 italic">
                    No significant rank differences found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
