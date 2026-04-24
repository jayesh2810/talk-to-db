import { useState } from 'react'

const HOP_COLORS = ['text-indigo-400', 'text-violet-400', 'text-purple-400', 'text-fuchsia-400']

export default function TraversalSteps({ steps }) {
  const [open, setOpen] = useState(true)

  if (!steps || steps.length === 0) return null

  return (
    <div className="rounded-lg border border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800 hover:bg-gray-750 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-medium">Graph traversal</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-900 text-purple-300 border border-purple-700 font-mono">
            {steps.length} hops
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
        <div className="p-3 bg-gray-900 border-t border-gray-700 space-y-3">
          {steps.map((step, idx) => {
            const hopColor = HOP_COLORS[Math.min(step.hop, HOP_COLORS.length - 1)]
            return (
              <div key={idx} className="flex gap-3">
                {/* Step number + connector */}
                <div className="flex flex-col items-center">
                  <div className={`w-6 h-6 rounded-full border flex items-center justify-center text-xs font-mono font-bold flex-shrink-0 border-gray-600 ${hopColor}`}>
                    {step.step}
                  </div>
                  {idx < steps.length - 1 && (
                    <div className="w-px flex-1 bg-gray-700 mt-1 min-h-[12px]" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 pb-1">
                  <p className="text-sm text-gray-200 leading-snug">
                    {step.description}
                  </p>
                  {step.detail && (
                    <p className="text-xs font-mono text-gray-500 mt-0.5 leading-relaxed break-words">
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
