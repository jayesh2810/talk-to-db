import { useState } from 'react'

const HOP_COLORS = ['text-indigo-400', 'text-violet-400', 'text-purple-400', 'text-fuchsia-400']

export default function TraversalSteps({ steps }) {
  const [open, setOpen] = useState(true)

  if (!steps || steps.length === 0) return null

  return (
    <div className="rounded-2xl border border-gray-700/50 overflow-hidden bg-gray-900/30 shadow-xl">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800/50 hover:bg-gray-800/80 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">Graph Traversal</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-mono font-bold">
            {steps.length} hops
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="p-4 bg-gray-900/50 border-t border-gray-700/50 space-y-4">
          {steps.map((step, idx) => {
            const hopColor = HOP_COLORS[Math.min(step.hop, HOP_COLORS.length - 1)]
            return (
              <div key={idx} className="flex gap-4">
                {/* Step number + connector */}
                <div className="flex flex-col items-center">
                  <div className={`w-6 h-6 rounded-full border flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0 border-gray-700 bg-gray-900 ${hopColor} shadow-sm`}>
                    {step.step}
                  </div>
                  {idx < steps.length - 1 && (
                    <div className="w-px flex-1 bg-gradient-to-b from-gray-700 to-transparent mt-1 min-h-[16px]" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 pb-2">
                  <p className="text-sm text-gray-200 leading-relaxed">
                    {step.description}
                  </p>
                  {step.detail && (
                    <p className="text-xs font-mono text-gray-500 mt-1 leading-relaxed break-words bg-gray-800/30 p-2 rounded-lg border border-gray-700/30">
                      {step.detail}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
