import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'

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

function StatusBadge({ segment }) {
  const colors = {
    active: 'bg-emerald-900 text-emerald-300 border-emerald-700',
    inactive: 'bg-gray-800 text-gray-300 border-gray-600',
    vip: 'bg-indigo-900 text-indigo-300 border-indigo-700',
    at_risk: 'bg-red-900 text-red-300 border-red-700',
    returning: 'bg-emerald-900 text-emerald-300 border-emerald-700',
    new: 'bg-gray-700 text-gray-300 border-gray-600',
    unknown: 'bg-gray-700 text-gray-300 border-gray-600',
  }
  const color = colors[segment?.toLowerCase()] || colors.unknown
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${color}`}>
      {segment?.toUpperCase()}
    </span>
  )
}

export default function CustomerDrawer({ customerId, onClose }) {
  const { getAuthHeader } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!customerId) return

    const fetchCustomer = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/customer/${encodeURIComponent(customerId)}`, {
          headers: {
            ...getAuthHeader(),
          },
        })
        if (!res.ok) throw new Error('Failed to fetch customer profile')
        const json = await res.json()
        setData(json)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    fetchCustomer()
  }, [customerId, getAuthHeader])

  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  if (!customerId) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      <div className="relative w-[480px] h-full bg-gray-900 border-l border-gray-800 shadow-2xl flex flex-col animate-slide-in">
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-900/80 backdrop-blur-md">
          <h2 className="text-lg font-semibold text-white">User profile</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          {loading ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-500 gap-3">
              <svg className="w-8 h-8 animate-spin text-indigo-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span className="text-sm">Loading profile...</span>
            </div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center text-red-400 text-center gap-2">
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm">{error}</p>
            </div>
          ) : (
            <>
              <CollapsibleSection title="Profile" defaultOpen={false}>
                <div className="grid grid-cols-2 gap-y-4 gap-x-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">User id</span>
                    <span className="text-sm font-mono text-gray-200">{data.profile.id}</span>
                  </div>
                  {data.profile.age != null && (
                    <div className="flex flex-col gap-1">
                      <span className="text-[10px] text-gray-500 uppercase font-bold">Age</span>
                      <span className="text-sm text-gray-200">{data.profile.age}</span>
                    </div>
                  )}
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Name</span>
                    <span className="text-sm text-gray-200">{data.profile.name}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Segment</span>
                    <StatusBadge segment={data.profile.segment} />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">City</span>
                    <span className="text-sm text-gray-200">{data.profile.city}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Lifetime Value</span>
                    <span className="text-sm font-mono text-gray-200">${data.profile.lifetime_value?.toLocaleString()}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Signup Date</span>
                    <span className="text-sm text-gray-200">{data.profile.signup_date}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-gray-500 uppercase font-bold">Acquisition</span>
                    <span className="text-sm text-gray-200">{data.profile.acq_channel}</span>
                  </div>
                </div>
              </CollapsibleSection>

              <CollapsibleSection title="Churn Risk" defaultOpen={false}>
                <div className="flex flex-col items-center gap-6">
                  <div className="relative w-32 h-32">
                    <svg className="w-full h-full" viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="45" fill="none" stroke="#1f2937" strokeWidth="10" />
                      <circle
                        cx="50" cy="50" r="45" fill="none"
                        stroke={data.churn.score > 0.7 ? '#ef4444' : data.churn.score > 0.4 ? '#f59e0b' : '#10b981'}
                        strokeWidth="10"
                        strokeDasharray={`${data.churn.score * 282.7} 282.7`}
                        strokeLinecap="round"
                        transform="rotate(-90 50 50)"
                      />
                      <text x="50" y="55" textAnchor="middle" className="fill-white text-2xl font-bold font-mono" style={{ fontSize: '20px' }}>
                        {Math.round(data.churn.score * 100)}%
                      </text>
                    </svg>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-500 mb-2 uppercase font-bold">Confidence: {Math.round(data.churn.confidence * 100)}%</p>
                    <div className="flex flex-col gap-2">
                      {data.churn.top_factors.map((f, i) => (
                        <div key={i} className="flex items-center justify-between gap-4 px-3 py-2 bg-gray-800 rounded-lg border border-gray-700 w-full max-w-xs">
                          <span className="text-xs text-gray-300">{f.factor.replace(/_/g, ' ')}</span>
                          <span className="text-xs font-mono text-indigo-400">+{Math.round(f.contribution * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CollapsibleSection>

              <CollapsibleSection title="Order History" defaultOpen={false}>
                <div className="space-y-3">
                  {data.orders.map((o, i) => (
                    <div key={i} className="border border-gray-800 rounded-lg overflow-hidden bg-gray-800/30">
                      <div className="px-3 py-2 flex items-center justify-between bg-gray-800/50">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-gray-400">{o.order_id}</span>
                          <span className="text-xs text-gray-300">{o.order_date}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-gray-200">${o.total_amount}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                            o.status === 'completed' ? 'border-emerald-700 text-emerald-400' :
                            o.status === 'returned' ? 'border-red-700 text-red-400' : 'border-gray-600 text-gray-400'
                          }`}>
                            {o.status}
                          </span>
                        </div>
                      </div>
                      <div className="p-3 border-t border-gray-800 space-y-2">
                        {o.items.map((item, ji) => (
                          <div key={ji} className="flex items-center justify-between text-xs">
                            <span className="text-gray-400">{item.product_name} <span className="text-gray-600 text-[10px]">({item.category})</span></span>
                            <div className="flex items-center gap-3 font-mono">
                              <span className="text-gray-300">{item.quantity}x ${item.unit_price}</span>
                              {item.returned && <span className="text-red-500 text-[10px] font-bold">RETURNED</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </CollapsibleSection>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
