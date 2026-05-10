import { useState, useEffect } from 'react'

function CollapsibleSection({ title, children, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  return (
    <div className="mb-4 border border-gray-800 rounded-lg overflow-hidden bg-gray-900/50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2 flex items-center justify-between bg-gray-800/50 hover:bg-gray-800 transition-colors text-left"
      >
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{title}</span>
        <svg className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && <div className="p-4">{children}</div>}
    </div>
  )
}

function ChurnGauge({ score }) {
  if (score === null || score === undefined) return (
    <p className="text-xs text-gray-500 text-center">Prediction unavailable</p>
  )
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? '#ef4444' : pct >= 40 ? '#f59e0b' : '#10b981'
  const label = pct >= 70 ? 'High Risk' : pct >= 40 ? 'Medium Risk' : 'Low Risk'
  const circumference = 2 * Math.PI * 45

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-32 h-32">
        <svg className="w-full h-full" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="45" fill="none" stroke="#1f2937" strokeWidth="10" />
          <circle
            cx="50" cy="50" r="45" fill="none"
            stroke={color}
            strokeWidth="10"
            strokeDasharray={`${(score * circumference).toFixed(1)} ${circumference}`}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
          />
          <text x="50" y="52" textAnchor="middle" fill="white" style={{ fontSize: '20px', fontWeight: 'bold', fontFamily: 'monospace' }}>
            {pct}%
          </text>
        </svg>
      </div>
      <span className="text-xs font-bold uppercase tracking-wider" style={{ color }}>{label}</span>
      <p className="text-[10px] text-gray-500 text-center">
        90-day churn probability via KumoRFM
      </p>
    </div>
  )
}

export default function CustomerDrawer({ userId, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    setError(null)
    fetch(`/api/user/${userId}`)
      .then(r => { if (!r.ok) throw new Error('Failed to fetch user profile'); return r.json() })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [userId])

  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  if (!userId) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-[460px] h-full bg-gray-900 border-l border-gray-800 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="text-base font-semibold text-white">User Deep Dive</h2>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">ID #{userId}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-0">
          {loading ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-500 gap-3">
              <svg className="w-8 h-8 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span className="text-sm">Loading profile…</span>
            </div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center text-red-400 text-center gap-2">
              <p className="text-sm">{error}</p>
            </div>
          ) : data && (
            <>
              {/* Profile */}
              <CollapsibleSection title="Profile">
                <div className="grid grid-cols-2 gap-y-4 gap-x-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">User ID</span>
                    <span className="text-sm font-mono text-gray-200">#{data.profile.user_id}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Status</span>
                    <span className={`text-[11px] font-bold ${data.profile.active ? 'text-emerald-400' : 'text-red-400'}`}>
                      {data.profile.active ? '● Active' : '● Inactive'}
                    </span>
                  </div>
                  {data.profile.age && (
                    <div className="flex flex-col gap-1">
                      <span className="text-[10px] text-gray-500 uppercase font-bold">Age</span>
                      <span className="text-sm text-gray-200">{data.profile.age}</span>
                    </div>
                  )}
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Total Orders</span>
                    <span className="text-sm font-mono text-gray-200">{data.orders.length}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Total Spent</span>
                    <span className="text-sm font-mono text-gray-200">
                      ${data.orders.reduce((s, o) => s + (o.price || 0), 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              </CollapsibleSection>

              {/* Churn Risk */}
              <CollapsibleSection title="Churn Risk (KumoRFM)">
                <ChurnGauge score={data.churn_score} />
              </CollapsibleSection>

              {/* Order History */}
              <CollapsibleSection title={`Order History (${data.orders.length})`}>
                {data.orders.length === 0 ? (
                  <p className="text-xs text-gray-500 text-center">No orders found</p>
                ) : (
                  <div className="space-y-2">
                    {data.orders.map((o, i) => (
                      <div key={i} className="border border-gray-800 rounded-lg p-3 bg-gray-800/30">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-mono text-gray-400">#{o.order_id}</span>
                          <span className="text-xs font-mono text-gray-200">${(o.price || 0).toFixed(2)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-300">{o.item_name || `Item #${o.item_id}`}</span>
                          <span className="text-[10px] text-gray-500">{o.date ? String(o.date).slice(0, 10) : '—'}</span>
                        </div>
                        {o.category && (
                          <span className="text-[10px] text-indigo-400 mt-1 inline-block">{o.category}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CollapsibleSection>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
